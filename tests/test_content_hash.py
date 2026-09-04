"""Paper identity: when are two uploads the same document?

WHY THIS MATTERS MORE THAN IT LOOKS
-----------------------------------
This hash decides whether User B is served an analysis produced from User A's
upload. The two failure directions are not equal:

    a MISSED match  -> one paper is analysed twice. Costs money. Harmless.
    a FALSE match   -> somebody is shown an analysis of a paper they did not
                       upload. Silently wrong, and wrong in a way that looks
                       completely plausible.

So the tests below are asymmetric on purpose. The "same paper" cases cover
only differences that carry no meaning, and the "different paper" cases are
deliberately subtle - a changed number, a negation, one different word - to
pin down that normalisation never reaches content.
"""

import pytest

from src.services.content_hash import (
    ANALYSIS_VERSION,
    content_hash,
    is_hashable,
    normalise_text,
)

PAPER = (
    "Attention Is All You Need. We propose the Transformer, a model "
    "architecture based solely on attention mechanisms, dispensing with "
    "recurrence and convolutions entirely. Experiments on two machine "
    "translation tasks show these models to be superior in quality while "
    "being more parallelizable and requiring significantly less time to train."
)


class TestTheSamePaperHashesTheSame:
    """Only meaningless differences may be normalised away."""

    def test_identical_text(self) -> None:
        assert content_hash(PAPER) == content_hash(PAPER)

    def test_leading_and_trailing_whitespace(self) -> None:
        assert content_hash(f"\n\n   {PAPER}   \n\t") == content_hash(PAPER)

    def test_runs_of_spaces(self) -> None:
        """PDF extractors insert arbitrary spacing depending on how they read
        columns. The same paper from two extractors differs mostly in this."""
        assert content_hash(PAPER.replace(" ", "   ")) == content_hash(PAPER)

    def test_line_endings(self) -> None:
        """Windows vs Unix vs old Mac. Never a content difference."""
        text = PAPER.replace(". ", ".\n")
        assert content_hash(text.replace("\n", "\r\n")) == content_hash(text)
        assert content_hash(text.replace("\n", "\r")) == content_hash(text)

    def test_blank_lines_and_page_breaks(self) -> None:
        assert content_hash(PAPER.replace(". ", ".\n\n\n\f")) == content_hash(
            PAPER.replace(". ", ". ")
        )

    def test_ligatures_and_compatibility_forms(self) -> None:
        """NFKC folds the "fi" ligature and non-breaking spaces onto their
        ordinary forms. Two PDFs of one paper routinely differ only here."""
        assert content_hash("the ﬁnal classiﬁer") == content_hash("the final classifier")
        assert content_hash("a b") == content_hash("a b")

    def test_a_realistic_re_extraction(self) -> None:
        """Everything above at once, which is what a second extraction of the
        same PDF actually looks like."""
        messy = "\r\n\r\n  " + PAPER.replace(" ", "  ").replace(". ", ".\r\n\r\n") + "\n \f "
        assert content_hash(messy) == content_hash(PAPER)


class TestDifferentPapersHashDifferently:
    """The dangerous direction. Every case here is a SMALL difference."""

    def test_one_different_word(self) -> None:
        assert content_hash(PAPER) != content_hash(PAPER.replace("superior", "inferior"))

    def test_a_changed_number(self) -> None:
        assert content_hash("we report 41.8 BLEU") != content_hash("we report 41.9 BLEU")

    def test_a_negation(self) -> None:
        """The difference between a finding and its opposite."""
        assert content_hash("the effect was significant") != content_hash(
            "the effect was not significant"
        )

    def test_case_is_content(self) -> None:
        """NOT lowercased. "US" and "us" differ, and so do author names."""
        assert content_hash("Brown et al.") != content_hash("brown et al.")

    def test_punctuation_is_content(self) -> None:
        """NOT stripped: it separates a citation from a sentence."""
        assert content_hash("Smith, J. (2019)") != content_hash("Smith J 2019")

    def test_word_order(self) -> None:
        assert content_hash("training improves accuracy") != content_hash(
            "accuracy improves training"
        )

    def test_an_added_sentence(self) -> None:
        assert content_hash(PAPER) != content_hash(PAPER + " We also release our code.")

    def test_two_unrelated_papers(self) -> None:
        assert content_hash(PAPER) != content_hash(
            "Deep Residual Learning for Image Recognition. We present a "
            "residual learning framework to ease the training of networks."
        )


class TestHashShape:
    def test_it_is_sha256_hex(self) -> None:
        digest = content_hash(PAPER)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_it_is_stable_across_runs(self) -> None:
        """No salt, no randomisation: a hash computed today must match one
        computed last month, or the cache silently empties on every deploy."""
        # A pinned, exact value. An `or len(...) == 64` fallback here would
        # make the test unfailable, which is worse than not having it: the
        # whole point is to catch a change to the normalisation rule that
        # silently empties the cache on deploy.
        assert (
            content_hash("ResearchForge")
            == "be21a08e39d93f13e57d43fcb5584dbb65e030aac008df6650fd7d34374987bf"
        )

    def test_encoding_is_explicit_so_platforms_agree(self) -> None:
        """Development is Windows, deployment is Linux. A default-encoding
        difference would split the cache in two."""
        assert content_hash("naïve Bayes café") == content_hash("naïve Bayes café")


class TestTooLittleTextIsNotCached:
    """A near-empty extraction would collide with every other near-empty one,
    and one of those documents would be served the other's analysis."""

    @pytest.mark.parametrize("text", ["", "   ", "\n\n\n", "Page 1", "Figure 3.", "A" * 199])
    def test_thin_extractions_are_refused(self, text) -> None:
        assert is_hashable(text) is False

    def test_a_real_paper_is_accepted(self) -> None:
        assert is_hashable(PAPER) is True

    def test_the_threshold_is_on_NORMALISED_length(self) -> None:
        """Padding with whitespace must not make a thin document look
        substantial - the whitespace is exactly what gets removed."""
        assert is_hashable("short" + " " * 5000) is False


class TestNormalisation:
    def test_empty_input_is_safe(self) -> None:
        assert normalise_text("") == ""
        assert len(content_hash("")) == 64

    def test_it_does_not_alter_meaningful_content(self) -> None:
        assert normalise_text("The BLEU score was 41.8.") == "The BLEU score was 41.8."


class TestAnalysisVersion:
    def test_there_is_one(self) -> None:
        assert isinstance(ANALYSIS_VERSION, str) and ANALYSIS_VERSION

    def test_it_is_declared_in_exactly_one_place(self) -> None:
        """The point of the version is that bumping it retires every entry at
        once. A second copy anywhere would mean bumping one and not the other,
        and serving stale analyses under a new pipeline."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        assignments = [
            path
            for path in root.rglob("*.py")
            if "ANALYSIS_VERSION =" in path.read_text(encoding="utf-8")
        ]
        assert [p.name for p in assignments] == ["content_hash.py"]
