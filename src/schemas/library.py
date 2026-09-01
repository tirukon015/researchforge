"""Schemas for the research library: saved papers and literature reviews.

These are the contract between the API and the frontend. They are kept
separate from `analysis.py`, which describes what the MODEL produces: the
models here describe what the DATABASE stores, and the two change for
different reasons.

Every model forbids extra fields, so a typo in a request body is a 422
naming the offending key rather than a silently ignored value.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.analysis import (
    DocumentInfo,
    LiteratureReview,
    ResearchGaps,
    Summary,
)

STRICT = ConfigDict(extra="forbid")


class PaperStatus(StrEnum):
    """Lifecycle of a paper in the library.

    Mirrors the CHECK constraint on papers.status in migration 001, so an
    invalid value is rejected by the API before it can be rejected, less
    helpfully, by Postgres.
    """

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SortOrder(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"
    TITLE = "title"


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #


class SavePaperRequest(BaseModel):
    """Save a completed analysis into the library.

    The analysis is passed back rather than re-run: the client already
    paid for it, and re-generating on save would double the cost and
    could return a different answer than the one the user chose to keep.
    """

    model_config = STRICT

    title: str = Field(
        min_length=1,
        max_length=500,
        description="Display title. Falls back to the filename when unknown.",
    )
    filename: str = Field(min_length=1, max_length=500)
    file_size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = Field(default=None, max_length=200)

    document: DocumentInfo
    summary: Summary
    research_gaps: ResearchGaps
    literature_review: LiteratureReview
    model_used: str = Field(min_length=1, max_length=200)


class CrossReviewRequest(BaseModel):
    """Generate one literature review across several saved papers."""

    model_config = STRICT

    # A "cross-paper" review of one paper is just that paper's own review,
    # which already exists - so the floor is two. The ceiling keeps the
    # prompt inside the model's context and the request inside the
    # function's time limit.
    paper_ids: list[str] = Field(
        min_length=2,
        max_length=12,
        description="IDs of saved papers to review together (2-12).",
    )
    title: str | None = Field(
        default=None,
        max_length=300,
        description="Optional name. A dated default is used when omitted.",
    )


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #


class PaperListItem(BaseModel):
    """One row in the library list.

    Deliberately without the analysis body: a list of thirty papers does
    not need thirty full analyses, and sending them would make the
    library slower the more the user relies on it.
    """

    model_config = STRICT

    id: str
    title: str
    filename: str
    status: PaperStatus
    page_count: int | None = None
    file_size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime
    has_analysis: bool = Field(description="Whether a stored analysis exists for this paper.")
    gap_count: int | None = Field(
        default=None,
        description="Gaps identified, or null where the analysis found none it could support.",
    )


class PaperListResponse(BaseModel):
    model_config = STRICT

    papers: list[PaperListItem]
    total: int = Field(description="Papers matching the filter, before paging.")


class PaperDetail(BaseModel):
    """One paper with its most recent analysis, if it has one."""

    model_config = STRICT

    id: str
    title: str
    filename: str
    status: PaperStatus
    page_count: int | None = None
    extracted_characters: int | None = None
    file_size_bytes: int | None = None
    content_type: str | None = None
    created_at: datetime
    updated_at: datetime

    # Absent when the paper was saved without an analysis, or when the
    # analysis failed. The UI must handle that rather than assume.
    summary: Summary | None = None
    research_gaps: ResearchGaps | None = None
    literature_review: LiteratureReview | None = None
    model_used: str | None = None
    chunk_count: int | None = None
    truncated: bool | None = None


class ReviewPaperRef(BaseModel):
    """A paper a review was built from, named so the claim is checkable."""

    model_config = STRICT

    id: str
    title: str
    filename: str


class ReviewRecord(BaseModel):
    model_config = STRICT

    id: str
    title: str
    model_used: str
    content: LiteratureReview
    paper_count: int
    papers: list[ReviewPaperRef]
    created_at: datetime


class ReviewListResponse(BaseModel):
    model_config = STRICT

    reviews: list[ReviewRecord]
    total: int


class DeleteResponse(BaseModel):
    model_config = STRICT

    id: str
    deleted: bool


class LibraryStats(BaseModel):
    """Counts for the dashboard overview.

    Every figure is a real count from the database. When storage is not
    configured the endpoint returns 503 rather than zeros, because zero
    is a claim ("you have no papers") and an unconfigured library is not
    in a position to make it.
    """

    model_config = STRICT

    papers_analysed: int
    research_gaps_found: int
    literature_reviews: int
    saved_papers: int
