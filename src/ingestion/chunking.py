"""Splitting long papers into analysable pieces.

WHY THIS IS DELIBERATELY MINIMAL
--------------------------------
The obvious instinct is "papers are long, so always chunk". That is wrong here,
and expensively so.

Claude Opus 5 has a **1,000,000-token context window**. A typical research paper
runs 5,000-25,000 tokens; even a 100-page thesis is around 60,000. All of those
fit whole, with room to spare. Chunking such a paper would actively make the
output worse: the model could no longer see that the limitation admitted in
section 6 undercuts the claim made in section 3, and cross-section reasoning is
exactly what gap analysis depends on.

So the strategy is:

    paper fits  -> send it whole (one chunk, full cross-section context)
    paper huge  -> map-reduce: analyse each chunk, then combine

`Settings.long_paper_char_threshold` is the switch. This is the "simplest
reliable implementation" the brief asked for - the complexity only appears for
the rare document that genuinely needs it.

Boundaries are chosen at paragraph breaks where possible, because cutting a
sentence in half at a fixed offset is how chunking corrupts meaning. Overlap
carries context across each seam.
"""

import logging

logger = logging.getLogger(__name__)

# How far back we will look for a clean paragraph/sentence boundary before
# giving up and cutting at the hard offset. Expressed as a fraction of chunk
# size so it scales with configuration.
_BOUNDARY_SEARCH_FRACTION = 0.2


def needs_chunking(text: str, threshold: int) -> bool:
    """Whether this text is too long to analyse in a single request."""
    return len(text) > threshold


def _find_boundary(text: str, start: int, ideal_end: int) -> int:
    """Find a clean place to cut at or before `ideal_end`.

    Prefers a paragraph break, then a sentence end, then the hard offset.
    """
    if ideal_end >= len(text):
        return len(text)

    window = max(1, int((ideal_end - start) * _BOUNDARY_SEARCH_FRACTION))
    floor = max(start + 1, ideal_end - window)

    paragraph = text.rfind("\n\n", floor, ideal_end)
    if paragraph != -1:
        return paragraph + 2

    sentence = text.rfind(". ", floor, ideal_end)
    if sentence != -1:
        return sentence + 2

    return ideal_end


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Split `text` into overlapping chunks at natural boundaries.

    Returns `[text]` unchanged when it already fits - the caller should not
    have to special-case the common path.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= chunk_size:
        # Otherwise each step forward is <= 0 and the loop never terminates.
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = _find_boundary(text, start, min(start + chunk_size, len(text)))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= len(text):
            break

        # Step forward by chunk minus overlap, measured from the ACTUAL cut so
        # the overlap is real even when the boundary moved backwards.
        start = max(start + 1, end - overlap)

    logger.info("split %d chars into %d chunks", len(text), len(chunks))
    return chunks
