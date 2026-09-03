"""Literature reviews built across several saved papers.

The single-paper review is produced by `POST /api/analyze` as part of one
analysis. These endpoints cover the other case: one review over a set of papers
the user selected from their library.

The review records which papers it was built from, and the response returns
them. That is what lets the interface claim "based on 3 papers" and have the
claim be checkable rather than merely asserted.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.analyze import get_provider, rate_limit_headers
from src.api.papers import get_library
from src.config import Settings, get_settings
from src.db import NotFoundError, PaperRepository, RepositoryError
from src.rag.llm import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
)
from src.schemas.library import (
    CrossReviewRequest,
    DeleteResponse,
    ReviewListResponse,
    ReviewRecord,
)
from src.services.cross_review import generate_cross_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reviews", tags=["Literature reviews"])


@router.post(
    "/cross",
    response_model=ReviewRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a literature review across several saved papers",
    responses={
        404: {"description": "One or more selected papers are not in the library"},
        429: {"description": "The AI provider is rate limiting or its quota is spent"},
        502: {"description": "The AI service failed or returned unusable output"},
        503: {"description": "The library or the AI credentials are unavailable"},
    },
)
async def create_cross_review(
    request: CrossReviewRequest,
    library: PaperRepository = Depends(get_library),
    provider: LLMProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
) -> ReviewRecord:
    """Review several papers together and save the result.

    Every selected paper must still exist and must carry a stored analysis. A
    review that silently covered four of the five papers the user chose would
    be worse than an error, because the interface would still report five.
    """
    try:
        papers = await library.get_papers_for_review(request.paper_ids)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    without_analysis = [p.title for p in papers if p.summary is None]
    if without_analysis:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "These papers have no stored analysis yet, so there is nothing to "
                f"review: {', '.join(without_analysis)}."
            ),
        )

    try:
        content = generate_cross_review(papers=papers, provider=provider, settings=settings)
    except LLMCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LLMRateLimitError as exc:
        # Before LLMError, which it subclasses. A cross-paper review is a
        # single expensive call, so telling the user to wait the stated time
        # matters more here than anywhere else.
        logger.warning("rate limited generating cross-review (exhausted=%s)", exc.quota_exhausted)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers=rate_limit_headers(exc),
        ) from exc
    except LLMResponseError as exc:
        logger.warning("unusable cross-review output: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except LLMError as exc:
        logger.warning("cross-review generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    title = (request.title or "").strip() or (
        f"Review of {len(papers)} papers, {datetime.now(UTC).strftime('%d %b %Y')}"
    )

    try:
        return await library.save_review(
            title=title,
            model_used=provider.model_name,
            content=content,
            paper_ids=[p.id for p in papers],
        )
    except RepositoryError as exc:
        # The review was generated but could not be stored. Say so rather than
        # returning it as though it had been saved: the user would look for it
        # in the library and not find it.
        logger.error("cross-review generated but not saved: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The review was generated but could not be saved to your library. Please try again."
            ),
        ) from exc


@router.get(
    "",
    response_model=ReviewListResponse,
    summary="List saved literature reviews, newest first",
)
async def list_reviews(
    limit: int = Query(default=50, ge=1, le=100),
    library: PaperRepository = Depends(get_library),
) -> ReviewListResponse:
    try:
        reviews, total = await library.list_reviews(limit=limit)
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ReviewListResponse(reviews=reviews, total=total)


@router.get(
    "/{review_id}",
    response_model=ReviewRecord,
    summary="One saved literature review",
    responses={404: {"description": "Not found"}},
)
async def get_review(
    review_id: str,
    library: PaperRepository = Depends(get_library),
) -> ReviewRecord:
    try:
        return await library.get_review(review_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.delete(
    "/{review_id}",
    response_model=DeleteResponse,
    summary="Delete a saved literature review",
    responses={404: {"description": "Not found"}},
)
async def delete_review(
    review_id: str,
    library: PaperRepository = Depends(get_library),
) -> DeleteResponse:
    try:
        deleted = await library.delete_review(review_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return DeleteResponse(id=review_id, deleted=deleted)
