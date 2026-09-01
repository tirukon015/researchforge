"""Orchestration for the paper-analysis workflow.

THE PIPELINE
------------
    PDF bytes
      -> validate + extract text        (src.ingestion.pdf)
      -> clean                          (src.ingestion.pdf.clean_text)
      -> fits in context?
           yes -> use the whole paper
           no  -> chunk, digest each chunk, concatenate digests
      -> three independent structured LLM calls
           summary / research gaps / literature review
      -> AnalysisResponse

WHY THE THREE CALLS ARE SEPARATE
--------------------------------
They are different tasks with different evidence rules, and separating them
means a failure in one does not corrupt the others. It also lets each be
re-run or improved on its own. See `src/prompts/analysis.py`.

WHY THERE IS NO DATABASE HERE
-----------------------------
The MVP is deliberately stateless: a paper is uploaded, analysed, and returned
in one request/response cycle. Nothing in this flow needs to outlive it. That
keeps Milestone 2 honestly separate instead of adding persistence the working
feature does not yet require.
"""

import logging

from src.config import Settings
from src.ingestion.chunking import chunk_text, needs_chunking
from src.ingestion.pdf import ExtractedDocument, extract_document
from src.prompts.analysis import (
    CHUNK_DIGEST_PROMPT,
    DIGEST_PREAMBLE,
    GAPS_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
    LITERATURE_REVIEW_PROMPT,
    SUMMARY_PROMPT,
)
from src.rag.llm import LLMProvider
from src.schemas.analysis import (
    AnalysisResponse,
    DocumentInfo,
    LiteratureReview,
    ResearchGaps,
    Summary,
)

logger = logging.getLogger(__name__)


def _build_analysis_content(
    document: ExtractedDocument, provider: LLMProvider, settings: Settings
) -> tuple[str, int]:
    """Return the text to analyse, plus how many chunks it came from.

    For an ordinary paper this returns the text unchanged and a chunk count of
    1 - the model sees the whole document, which is what makes cross-section
    reasoning possible. Only a genuinely oversized paper takes the map step.
    """
    if not needs_chunking(document.text, settings.long_paper_char_threshold):
        return document.text, 1

    chunks = chunk_text(
        document.text,
        chunk_size=settings.long_paper_chunk_size,
        overlap=settings.long_paper_chunk_overlap,
    )
    logger.info(
        "paper exceeds %d chars - digesting %d chunks",
        settings.long_paper_char_threshold,
        len(chunks),
    )

    digests: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        digest = provider.generate_text(
            system=GROUNDING_SYSTEM_PROMPT,
            prompt=CHUNK_DIGEST_PROMPT.format(index=index, total=len(chunks), content=chunk),
        )
        digests.append(f"--- Section {index} of {len(chunks)} ---\n{digest}")

    combined = DIGEST_PREAMBLE + "\n\n" + "\n\n".join(digests)
    return combined, len(chunks)


def analyse_paper(
    *,
    data: bytes,
    filename: str,
    provider: LLMProvider,
    settings: Settings,
) -> AnalysisResponse:
    """Run the full analysis on an uploaded PDF.

    Raises `PdfExtractionError` for bad input and `LLMError` for generation
    failures. Both are translated to HTTP status codes by the API layer; this
    function never returns a partial or invented result.
    """
    document = extract_document(data, filename=filename)
    content, chunk_count = _build_analysis_content(document, provider, settings)

    # Three independent calls. Deliberately sequential: they are unrelated, and
    # running them in parallel would multiply the peak rate-limit burden for a
    # latency win that does not matter on a single upload.
    summary = provider.generate_structured(
        system=GROUNDING_SYSTEM_PROMPT,
        prompt=SUMMARY_PROMPT.format(content=content),
        output_model=Summary,
    )
    gaps = provider.generate_structured(
        system=GROUNDING_SYSTEM_PROMPT,
        prompt=GAPS_PROMPT.format(content=content),
        output_model=ResearchGaps,
    )
    review = provider.generate_structured(
        system=GROUNDING_SYSTEM_PROMPT,
        prompt=LITERATURE_REVIEW_PROMPT.format(content=content),
        output_model=LiteratureReview,
    )

    logger.info("analysis complete for %s (%d chunks)", filename, chunk_count)
    return AnalysisResponse(
        document=DocumentInfo(
            filename=filename,
            page_count=document.page_count,
            extracted_characters=document.character_count,
            chunk_count=chunk_count,
            # Nothing is silently dropped: an oversized paper is digested
            # section by section, never truncated.
            truncated=False,
        ),
        summary=summary,
        research_gaps=gaps,
        literature_review=review,
        model_used=provider.model_name,
    )
