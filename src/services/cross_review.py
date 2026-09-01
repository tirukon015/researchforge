"""Generate one literature review across several saved papers.

WHY THIS READS STORED ANALYSES RATHER THAN THE ORIGINAL PDFS
------------------------------------------------------------
The obvious implementation would re-extract every selected PDF and send the
full text of all of them. That is wrong twice over: the combined text of a
dozen papers overruns the context window, and the papers have already been
analysed once, so re-reading them pays for the same work twice.

Instead each paper contributes its stored summary, findings, limitations and
themes. Those are the parts a literature review actually draws on, they are
already grounded in the source, and they fit comfortably together.

The cost is honest and worth stating: this review is built on the analyses,
not on a fresh reading. It cannot surface something the original analysis
missed.
"""

import logging

from src.config import Settings
from src.prompts.analysis import (
    CROSS_REVIEW_PAPER_BLOCK,
    CROSS_REVIEW_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
)
from src.rag.llm import LLMProvider
from src.schemas.analysis import LiteratureReview
from src.schemas.library import PaperDetail

logger = logging.getLogger(__name__)

# Guards the prompt against a pathological paper. A single analysis section
# should be a paragraph, not a chapter; anything past this is truncated so one
# outlier cannot crowd out the other papers.
_MAX_SECTION_CHARS = 4_000


def _clip(text: str | None, limit: int = _MAX_SECTION_CHARS) -> str:
    if not text:
        return "Not available from this paper."
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " [truncated]"


def _bullets(items: list[str] | None, limit: int = 12) -> str:
    """Render a list for the prompt, or say plainly that it is empty."""
    if not items:
        return "  (none reported)"
    return "\n".join(f"  - {_clip(item, 500)}" for item in items[:limit])


def build_paper_block(paper: PaperDetail, index: int, total: int) -> str:
    """One paper's contribution to the combined prompt."""
    summary = paper.summary
    gaps = paper.research_gaps
    review = paper.literature_review

    limitations: list[str] = []
    if gaps and not gaps.insufficient_evidence:
        limitations = list(gaps.stated_limitations)

    themes: list[str] = []
    if review and not review.insufficient_evidence:
        themes = list(review.major_themes)

    return CROSS_REVIEW_PAPER_BLOCK.format(
        index=index,
        total=total,
        title=paper.title,
        problem=_clip(summary.research_problem if summary else None),
        methodology=_clip(summary.methodology if summary else None),
        findings=_bullets(summary.key_findings if summary else None),
        limitations=_bullets(limitations),
        themes=_bullets(themes),
    )


def build_prompt(papers: list[PaperDetail]) -> str:
    """Assemble the full cross-paper prompt from the selected papers."""
    total = len(papers)
    blocks = [build_paper_block(p, i, total) for i, p in enumerate(papers, start=1)]
    return CROSS_REVIEW_PROMPT.format(count=total, content="\n\n".join(blocks))


def generate_cross_review(
    *,
    papers: list[PaperDetail],
    provider: LLMProvider,
    settings: Settings,
) -> LiteratureReview:
    """Produce one review covering every supplied paper.

    Raises `LLMError` or a subclass on failure, exactly as the single-paper
    pipeline does, so the API layer maps it to the same status codes and the
    frontend needs no new error vocabulary.
    """
    del settings  # accepted for symmetry with analyse_paper; nothing needed yet

    logger.info("cross-paper review over %d papers", len(papers))
    return provider.generate_structured(
        system=GROUNDING_SYSTEM_PROMPT,
        prompt=build_prompt(papers),
        output_model=LiteratureReview,
    )
