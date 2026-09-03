"""Tests for PDF ingestion, chunking, and the /api/analyze endpoint.

⚠️ NO NETWORK CALLS. Every test runs offline and spends zero tokens. The LLM is
replaced by `FakeLLMProvider`, which satisfies the same interface the real
Anthropic provider does. Root CLAUDE.md §9 requires exactly this: the embedding
tests already use a fake provider, and generation follows the same rule.

The PDFs are real PDF bytes built by `tests/pdf_fixtures.py`, so extraction is
genuinely exercised - pypdf really parses them.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.analyze import get_provider
from src.config import Settings, get_settings
from src.ingestion.chunking import chunk_text, needs_chunking
from src.ingestion.pdf import PdfExtractionError, clean_text, extract_document
from src.main import app
from src.rag.llm.base import LLMCredentialsError, LLMProvider, LLMResponseError
from src.schemas.analysis import LiteratureReview, ResearchGaps, Summary
from tests.auth_fixtures import USER_A, sign_in_as
from tests.pdf_fixtures import (
    build_empty_text_pdf,
    build_long_pdf,
    build_pdf,
    build_text_pdf,
)

PAPER_TEXT = (
    "Deep Learning for Protein Folding.\n\n"
    "Abstract. We investigate whether transformer models predict tertiary "
    "structure from sequence alone. Prior work by Chen established a baseline "
    "of 61 percent accuracy.\n\n"
    "Methodology. We trained on 12,000 sequences and evaluated on a held-out "
    "set of 400.\n\n"
    "Results. Our model reached 74 percent accuracy.\n\n"
    "Limitations. We did not evaluate on membrane proteins, and the training "
    "set covers only eukaryotes.\n\n"
) * 3


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _summary() -> Summary:
    return Summary(
        research_problem="Whether transformers predict protein structure.",
        methodology="Trained on 12,000 sequences, evaluated on 400.",
        key_findings=["Reached 74 percent accuracy."],
        conclusion="Transformers are viable for this task.",
        insufficient_evidence=[],
    )


def _gaps() -> ResearchGaps:
    return ResearchGaps(
        stated_limitations=["No evaluation on membrane proteins."],
        identified_gaps=[
            {
                "gap": "Membrane proteins are unevaluated.",
                "why_it_matters": "They are a large drug-target class.",
                "evidence": "We did not evaluate on membrane proteins.",
            }
        ],
        insufficient_evidence=False,
        evidence_note="",
    )


def _review() -> LiteratureReview:
    return LiteratureReview(
        scope_note="Drawn only from related work discussed in this paper.",
        major_themes=["Sequence-based structure prediction."],
        relevant_findings=["Chen established a 61 percent baseline."],
        comparisons=["This work improves on Chen by 13 points."],
        research_trends=["A shift toward transformer architectures."],
        limitations=["Prior work is limited to eukaryotes."],
        future_directions=["Extend to membrane proteins."],
        insufficient_evidence=False,
    )


class FakeLLMProvider(LLMProvider):
    """Offline stand-in for a real provider. Records what it was asked."""

    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.structured_calls: list[type] = []
        self.text_calls: list[str] = []

    @property
    def model_name(self) -> str:
        return "fake-model-v1"

    def generate_structured(self, *, system, prompt, output_model):
        if self.fail_with:
            raise self.fail_with
        self.structured_calls.append(output_model)
        return {
            Summary: _summary,
            ResearchGaps: _gaps,
            LiteratureReview: _review,
        }[output_model]()

    def generate_text(self, *, system, prompt):
        if self.fail_with:
            raise self.fail_with
        self.text_calls.append(prompt)
        return "Digest of one section: methodology and results were reported."


@pytest.fixture
def client():
    """A TestClient whose LLM provider is the offline fake, signed in.

    /api/analyze requires an account: each call is three passes against a paid,
    rate-limited quota, so an open endpoint would let anyone spend the
    allowance. These tests are about the analysis pipeline rather than the
    door, so an identity is supplied; tests/test_auth.py checks the door.
    """
    fake = FakeLLMProvider()
    sign_in_as(USER_A)
    app.dependency_overrides[get_provider] = lambda: fake
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    test_client = TestClient(app)
    test_client.fake = fake  # type: ignore[attr-defined]
    yield test_client
    app.dependency_overrides.clear()


def _upload(client, data, name="paper.pdf", mime="application/pdf"):
    return client.post("/api/analyze", files={"file": (name, data, mime)})


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


class TestTextExtraction:
    """Real PDFs, really parsed."""

    def test_text_is_extracted_from_a_real_pdf(self) -> None:
        doc = extract_document(build_text_pdf(PAPER_TEXT), filename="p.pdf")
        assert "protein" in doc.text.lower()
        assert doc.page_count == 1

    def test_every_page_is_read(self) -> None:
        doc = extract_document(
            build_pdf(["First page content here. " * 20, "Second page content. " * 20]),
            filename="p.pdf",
        )
        assert doc.page_count == 2
        assert "First page" in doc.text and "Second page" in doc.text

    def test_hyphenated_line_breaks_are_rejoined(self) -> None:
        assert clean_text("evalu-\nation") == "evaluation"

    def test_ligatures_are_normalised(self) -> None:
        assert clean_text("the ﬁrst ﬂow") == "the first flow"

    def test_empty_file_is_rejected(self) -> None:
        with pytest.raises(PdfExtractionError, match="empty"):
            extract_document(b"", filename="p.pdf")

    def test_non_pdf_bytes_are_rejected(self) -> None:
        with pytest.raises(PdfExtractionError, match="not a PDF"):
            extract_document(b"MZ\x90\x00 this is an executable", filename="p.exe")

    def test_pdf_without_a_text_layer_is_rejected(self) -> None:
        """A scanned paper must fail clearly, not return an empty analysis."""
        with pytest.raises(PdfExtractionError, match="scan|OCR"):
            extract_document(build_empty_text_pdf(), filename="scan.pdf")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


class TestChunking:
    def test_short_text_is_not_chunked(self) -> None:
        assert chunk_text("short text", chunk_size=1000, overlap=50) == ["short text"]

    def test_long_text_is_split(self) -> None:
        text = ("A sentence that is reasonably long. " * 100).strip()
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1
        assert all(len(c) <= 500 for c in chunks)

    def test_chunking_preserves_the_tail(self) -> None:
        text = "start " + ("filler " * 200) + "FINALMARKER"
        chunks = chunk_text(text, chunk_size=300, overlap=30)
        assert "FINALMARKER" in chunks[-1]

    def test_threshold_controls_activation(self) -> None:
        assert needs_chunking("x" * 501, 500)
        assert not needs_chunking("x" * 499, 500)

    def test_overlap_must_be_smaller_than_chunk(self) -> None:
        with pytest.raises(ValueError, match="smaller"):
            chunk_text("abc" * 100, chunk_size=10, overlap=10)


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


class TestAnalyzeEndpoint:
    def test_health_still_works(self, client) -> None:
        """The new router must not disturb the platform health check."""
        assert client.get("/health").status_code == 200

    def test_valid_pdf_returns_200(self, client) -> None:
        assert _upload(client, build_text_pdf(PAPER_TEXT)).status_code == 200

    def test_all_three_sections_are_returned(self, client) -> None:
        body = _upload(client, build_text_pdf(PAPER_TEXT)).json()
        assert set(body) >= {
            "document",
            "summary",
            "research_gaps",
            "literature_review",
            "model_used",
        }

    def test_summary_output_is_structured(self, client) -> None:
        summary = _upload(client, build_text_pdf(PAPER_TEXT)).json()["summary"]
        assert summary["research_problem"]
        assert summary["methodology"]
        assert isinstance(summary["key_findings"], list)
        assert summary["conclusion"]

    def test_research_gap_output_is_structured(self, client) -> None:
        gaps = _upload(client, build_text_pdf(PAPER_TEXT)).json()["research_gaps"]
        assert gaps["stated_limitations"]
        gap = gaps["identified_gaps"][0]
        # Evidence is what stops a gap being an invention.
        assert {"gap", "why_it_matters", "evidence"} <= set(gap)

    def test_literature_review_output_is_structured(self, client) -> None:
        review = _upload(client, build_text_pdf(PAPER_TEXT)).json()["literature_review"]
        assert review["scope_note"], "the scope caveat must never be empty"
        assert isinstance(review["major_themes"], list)

    def test_document_metadata_is_measured_not_generated(self, client) -> None:
        doc = _upload(client, build_text_pdf(PAPER_TEXT), name="myfile.pdf").json()["document"]
        assert doc["filename"] == "myfile.pdf"
        assert doc["page_count"] == 1
        assert doc["extracted_characters"] > 0
        assert doc["truncated"] is False

    def test_three_separate_llm_calls_are_made(self, client) -> None:
        _upload(client, build_text_pdf(PAPER_TEXT))
        assert client.fake.structured_calls == [Summary, ResearchGaps, LiteratureReview]

    def test_invalid_file_type_returns_422(self, client) -> None:
        r = _upload(
            client,
            b"MZ\x90\x00 not a pdf",
            name="virus.exe",
            mime="application/octet-stream",
        )
        assert r.status_code == 422
        assert "not a PDF" in r.json()["detail"]

    def test_pdf_extension_on_non_pdf_content_is_still_rejected(self, client) -> None:
        """A renamed file must not get through on its extension alone."""
        r = _upload(client, b"just plain text, not a pdf at all", name="paper.pdf")
        assert r.status_code == 422

    def test_empty_pdf_returns_422(self, client) -> None:
        r = _upload(client, build_empty_text_pdf())
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "OCR" in detail or "scan" in detail

    def test_empty_upload_returns_422(self, client) -> None:
        assert _upload(client, b"").status_code == 422

    def test_oversized_upload_returns_413(self) -> None:
        sign_in_as(USER_A)
        app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, max_upload_size_mb=1
        )
        try:
            r = _upload(TestClient(app), b"%PDF-" + b"x" * (2 * 1024 * 1024))
            assert r.status_code == 413
            assert "limit" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.parametrize(
        ("provider", "expected_variable"),
        [("anthropic", "ANTHROPIC_API_KEY"), ("groq", "GROQ_API_KEY")],
    )
    def test_missing_credentials_returns_503(self, provider, expected_variable) -> None:
        """No API key must be a clear 503, never a 500 stack trace.

        Parametrised over both providers because the message has to name the
        variable the operator actually needs to set - naming the other vendor's
        would send them to fix the wrong thing.

        Signed in first: /api/analyze checks the caller BEFORE it checks its
        own configuration, deliberately, so a stranger cannot learn which key
        the deployment is missing. Reaching the 503 therefore requires an
        account.
        """
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None,
            llm_provider=provider,
            anthropic_api_key="",
            groq_api_key="",
            gemini_api_key="",
        )
        try:
            r = _upload(TestClient(app), build_text_pdf(PAPER_TEXT))
            assert r.status_code == 503
            assert expected_variable in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_malformed_ai_response_returns_502(self) -> None:
        """If the model returns something unusable we must fail, not invent."""
        broken = FakeLLMProvider(
            fail_with=LLMResponseError("output did not match the expected schema")
        )
        sign_in_as(USER_A)
        app.dependency_overrides[get_provider] = lambda: broken
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        try:
            r = _upload(TestClient(app), build_text_pdf(PAPER_TEXT))
            assert r.status_code == 502
            assert "schema" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_credentials_rejected_mid_flight_returns_503(self) -> None:
        bad = FakeLLMProvider(fail_with=LLMCredentialsError("key rejected"))
        sign_in_as(USER_A)
        app.dependency_overrides[get_provider] = lambda: bad
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        try:
            r = _upload(TestClient(app), build_text_pdf(PAPER_TEXT))
            assert r.status_code == 503
        finally:
            app.dependency_overrides.clear()


class TestLongPaperHandling:
    """The map-reduce path activates only past the configured threshold."""

    def test_ordinary_paper_is_analysed_whole(self, client) -> None:
        body = _upload(client, build_text_pdf(PAPER_TEXT)).json()
        assert body["document"]["chunk_count"] == 1
        assert client.fake.text_calls == [], "no digest step for a normal paper"

    def test_long_paper_is_chunked_and_digested(self) -> None:
        fake = FakeLLMProvider()
        sign_in_as(USER_A)
        app.dependency_overrides[get_provider] = lambda: fake
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None,
            long_paper_char_threshold=3_000,
            long_paper_chunk_size=1_500,
            long_paper_chunk_overlap=100,
        )
        try:
            r = _upload(TestClient(app), build_long_pdf(pages=12, chars_per_page=900))
            assert r.status_code == 200
            body = r.json()
            assert body["document"]["chunk_count"] > 1
            # One digest call per chunk, then the three analysis calls.
            assert len(fake.text_calls) == body["document"]["chunk_count"]
            assert len(fake.structured_calls) == 3
            assert body["document"]["truncated"] is False
        finally:
            app.dependency_overrides.clear()
