"""What makes two uploads "the same paper".

This module owns one decision and nothing else: given the text extracted from
a PDF, produce a stable identity for the document. Everything about the
analysis cache depends on that identity being right, so it lives alone, is
pure, and is heavily tested.

WHY NOT THE FILENAME
--------------------
The same paper arrives as `attention.pdf`, `Attention Is All You Need.pdf`,
and `1706.03762v7 (1).pdf`. Those are one paper. Meanwhile two unrelated
drafts both called `paper.pdf` are two. A filename says nothing about content,
and using it would produce both false matches and missed ones.

WHY NOT A HASH OF THE PDF BYTES
-------------------------------
Re-saving a PDF, stripping its metadata, or downloading it from a different
mirror changes the bytes while the paper is unchanged. Byte identity is far
too strict to be useful here.

So the identity is the hash of the EXTRACTED TEXT, after a deliberately small
amount of normalisation.

HOW CONSERVATIVE THE NORMALISATION IS, AND WHY
----------------------------------------------
Every normalisation step is a decision that two different things are the same.
Get that wrong and User B is served an analysis of a paper they did not
upload - a correctness failure far worse than a missed cache hit.

So the rule is narrow. It removes only differences that carry no meaning:

  * leading/trailing whitespace on the whole document and on each line
  * runs of whitespace collapsed to one space
  * blank lines removed
  * Windows/Mac line endings unified
  * Unicode normalised to NFKC, so a ligature or a full-width character
    matches its ordinary form

It does NOT lowercase, strip punctuation, remove numbers, drop stop words, or
touch anything a reader would consider content. A missed cache hit costs one
analysis. A false hit corrupts somebody's research.

THE VERSION
-----------
`ANALYSIS_VERSION` is declared here, next to the hash, because the cache key
is the pair. Bump it in this ONE place when the prompts, the response schema,
or the pipeline change in a way that would make an old result wrong. Old rows
are not deleted - they simply stop matching, so a bump is instantly reversible.
"""

import hashlib
import re
import unicodedata

# Bump when a stored analysis produced by an older pipeline should no longer be
# reused. This is the only place it is written down.
#
#   v1  initial: three grounded passes (summary, research gaps, literature
#       review) over the whole document.
ANALYSIS_VERSION = "v1"

# Any run of whitespace - spaces, tabs, newlines, non-breaking spaces - is one
# space. PDF extraction produces these almost at random depending on the
# extractor's column handling, and none of it is content.
_WHITESPACE = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Reduce extracted text to its meaningful content.

    Deliberately narrow: see the module docstring for what is NOT done and
    why. The output is what gets hashed, so any change to this function
    changes every future identity - which is what `ANALYSIS_VERSION` is for.
    """
    if not text:
        return ""

    # NFKC folds compatibility forms - the "fi" ligature, full-width Latin,
    # non-breaking spaces - onto their ordinary equivalents. Two PDFs of the
    # same paper from different producers routinely differ only in these.
    text = unicodedata.normalize("NFKC", text)

    # One space for any run of whitespace, then trim. This alone accounts for
    # most spurious differences between two extractions of the same document.
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def content_hash(text: str) -> str:
    """SHA-256 of the normalised text, as lowercase hex.

    SHA-256 rather than a faster non-cryptographic hash: a collision here
    would serve one paper's analysis for another, and the cost of hashing a
    document once is irrelevant beside three model calls.

    Encoded UTF-8 explicitly so the same text hashes identically regardless of
    the platform's default encoding - the deployment is Linux and development
    is Windows.
    """
    return hashlib.sha256(normalise_text(text).encode("utf-8")).hexdigest()


def is_hashable(text: str) -> bool:
    """Whether this extraction is substantial enough to key a cache on.

    A near-empty extraction - a scanned page with a stray character, a cover
    sheet - would hash to the same value for genuinely different documents,
    and one of them would then be served the other's analysis. Such uploads
    are analysed normally and simply not cached.

    200 characters is about a paragraph: comfortably below any real paper and
    comfortably above the accidental collisions this guards against.
    """
    return len(normalise_text(text)) >= 200
