"""The research library: save, list, open and delete papers.

EVERY ROUTE HERE IS PRIVATE
---------------------------
`get_library` depends on `require_user`, so there is no way to reach a paper
without a valid Supabase access token, and the repository it returns talks to
Postgres AS THAT USER. Ownership is therefore enforced by Row Level Security in
the database, not by a `WHERE user_id = ...` this module has to remember to
write. A new endpoint added below inherits the isolation automatically; one
that forgot to filter would return nothing rather than everything.

ERROR MAPPING
-------------
Status codes are chosen so the frontend can tell the cases apart without
parsing message text, the same contract `analyze.py` follows:

    401  not signed in, or the session expired
    404  the paper is not in the library, OR belongs to someone else
    409  deleting it would break a saved literature review
    503  the library is not connected, or could not be reached

404 covering "someone else's paper" is deliberate. RLS makes another user's row
unreadable, so the request comes back empty exactly as it would for a paper that
never existed - and answering 403 instead would turn the id in the URL into a
tool for confirming which papers other people hold.

503 rather than an empty list is the important one. An empty list is a claim
("you have no papers"), and a deployment with no database is not in a position
to make it. The interface says the library is not connected instead.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.auth import AuthUser, require_user
from src.config import Settings, get_settings
from src.db import (
    AuthExpiredError,
    ConflictError,
    NotFoundError,
    PaperRepository,
    RepositoryError,
    RepositoryUnavailableError,
    get_repository,
)
from src.schemas.library import (
    DeleteResponse,
    LibraryStats,
    PaperDetail,
    PaperListResponse,
    PaperStatus,
    SavePaperRequest,
    SortOrder,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/papers", tags=["Library"])

LIBRARY_UNAVAILABLE = (
    "The research library is not connected, so papers cannot be saved yet. "
    "Analysis still works, and results are available for this visit."
)

# A DIFFERENT failure from "no database", and worth its own sentence. The
# variable is set, the connection would succeed, and the library would then
# appear permanently empty because a publishable key cannot see past Row Level
# Security. Naming the required key TYPE is what makes this fixable without
# anyone having to read the source; no key value appears here or anywhere else
# in a response.
#
# It leads with the CAUSE rather than repeating "not connected", because the
# interface already prints that as a heading above this sentence, and a 503
# already says it to anyone reading the API directly.
LIBRARY_MISCONFIGURED = (
    "The server is configured with a Supabase publishable key, which is a "
    "public browser key and cannot read or write this data. "
    "SUPABASE_SERVICE_ROLE_KEY needs the project's secret server-side key "
    "instead. Analysis still works, and results are available for this visit."
)


def get_library(
    user: AuthUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> PaperRepository:
    """Build the repository as a FastAPI dependency, SCOPED TO THE CALLER.

    `require_user` runs first, so an unauthenticated request never reaches a
    repository at all - it is refused with 401 before any database work starts.
    The user's own access token is then handed to the repository, which is what
    makes Postgres apply that person's Row Level Security policies.

    Being a dependency rather than a module-level object is what makes the
    endpoints testable: the suite overrides this with an in-memory fake, so no
    test needs a database. It is also what lets an unconfigured deployment
    answer 503 instead of failing at import time.
    """
    repository = get_repository(settings, access_token=user.token, user_id=user.id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                LIBRARY_MISCONFIGURED
                if settings.supabase_key_is_publishable
                else LIBRARY_UNAVAILABLE
            ),
        )
    return repository


def _raise_for(exc: RepositoryError) -> None:
    """Translate a storage error into the right HTTP status."""
    if isinstance(exc, AuthExpiredError):
        # Before RepositoryUnavailableError, which it does not subclass but is
        # easily confused with: the library is fine, the credential is stale.
        # 401 is what tells the frontend to refresh the session rather than
        # showing "the library is down" to someone who only needs to sign in.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, RepositoryUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    # Anything else is ours, not the caller's. The message is already written
    # for a person and carries no internal detail.
    logger.warning("library request failed: %s", exc)
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "",
    response_model=PaperDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Save a completed analysis to the library",
    responses={503: {"description": "The library is not connected"}},
)
async def save_paper(
    request: SavePaperRequest,
    library: PaperRepository = Depends(get_library),
) -> PaperDetail:
    """Persist a paper and the analysis already produced for it.

    The analysis is sent back by the client rather than re-run. It has already
    been paid for, and re-generating on save would both double the cost and
    risk storing a different answer than the one the user chose to keep.
    """
    try:
        return await library.save_paper(request)
    except RepositoryError as exc:
        _raise_for(exc)
        raise  # unreachable; keeps the type checker honest


@router.get(
    "",
    response_model=PaperListResponse,
    summary="List saved papers, with search, filter and sort",
)
async def list_papers(
    search: str | None = Query(default=None, max_length=200),
    status_filter: PaperStatus | None = Query(default=None, alias="status"),
    sort: SortOrder = Query(default=SortOrder.NEWEST),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    library: PaperRepository = Depends(get_library),
) -> PaperListResponse:
    """One page of the library.

    `total` is the number of papers matching the filter before paging, so the
    interface can say "12 of 40" without under-reporting on every page but the
    last.
    """
    try:
        papers, total = await library.list_papers(
            search=search,
            status=status_filter.value if status_filter else None,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except RepositoryError as exc:
        _raise_for(exc)
        raise
    return PaperListResponse(papers=papers, total=total)


@router.get(
    "/stats",
    response_model=LibraryStats,
    summary="Real counts for the dashboard overview",
)
async def library_stats(
    library: PaperRepository = Depends(get_library),
) -> LibraryStats:
    """Counts derived from stored rows. Nothing here is estimated."""
    try:
        return await library.stats()
    except RepositoryError as exc:
        _raise_for(exc)
        raise


@router.get(
    "/{paper_id}",
    response_model=PaperDetail,
    summary="One paper with its most recent analysis",
    responses={404: {"description": "Not in the library"}},
)
async def get_paper(
    paper_id: str,
    library: PaperRepository = Depends(get_library),
) -> PaperDetail:
    try:
        return await library.get_paper(paper_id)
    except RepositoryError as exc:
        _raise_for(exc)
        raise


@router.delete(
    "/{paper_id}",
    response_model=DeleteResponse,
    summary="Remove a paper and its analyses",
    responses={
        404: {"description": "Not in the library"},
        409: {"description": "A saved literature review was built from it"},
    },
)
async def delete_paper(
    paper_id: str,
    library: PaperRepository = Depends(get_library),
) -> DeleteResponse:
    """Delete a paper.

    Refused with 409 when a saved review was generated from it. Cascading the
    delete would leave the review claiming more sources than it can still name,
    which is a quieter and worse failure than refusing.
    """
    try:
        deleted = await library.delete_paper(paper_id)
    except RepositoryError as exc:
        _raise_for(exc)
        raise
    return DeleteResponse(id=paper_id, deleted=deleted)
