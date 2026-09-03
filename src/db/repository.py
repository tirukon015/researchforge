"""Storage-independent interface for the research library.

WHY THIS FILE EXISTS
--------------------
Same argument as `src/rag/llm/base.py`: the API layer talks to this
interface, never to a vendor SDK or to raw SQL. The concrete
implementation lives in `supabase.py` and is built by `get_repository`,
so swapping Postgres hosts - or adding an in-process fake for tests -
is a new file plus one branch, not a rewrite of every endpoint.

It also means the entire library API can be written, typed, and tested
before any database exists, which is exactly the situation this project
is in.

**Nothing in this file may be vendor-specific.** No PostgREST, no HTTP
status codes, no Supabase types. Those belong in the implementation.
"""

from abc import ABC, abstractmethod

from src.schemas.analysis import LiteratureReview
from src.schemas.library import (
    LibraryStats,
    PaperDetail,
    PaperListItem,
    ReviewRecord,
    SavePaperRequest,
    SortOrder,
)


class RepositoryError(RuntimeError):
    """Base class for every storage failure.

    Wrapping driver errors in project-owned exceptions keeps HTTP status
    codes out of the data layer and driver classes out of the API layer.
    """


class RepositoryUnavailableError(RepositoryError):
    """Storage is not configured, or could not be reached.

    Separate from the others because it is a deployment problem rather
    than a user's fault: the API maps it to 503, and the interface tells
    the reader the library is not connected instead of implying they
    have no papers.
    """


class AuthExpiredError(RepositoryError):
    """The caller's credentials were refused by the database.

    Separate from `RepositoryUnavailableError` because it is neither the
    deployment's fault nor permanent: the user's access token aged out, and
    signing in again fixes it. The API maps this to 401 so the frontend can
    refresh the session or send the person to the sign-in page, rather than
    telling them the library is down.
    """


class NotFoundError(RepositoryError):
    """The requested record does not exist, OR IS NOT THE CALLER'S.

    Deliberately one error for both cases. Row Level Security makes another
    user's paper unreadable, so a request for it comes back with no rows,
    exactly as a request for a deleted paper does - and this class keeps that
    indistinguishable at the API too. Answering 403 for "exists but is not
    yours" and 404 for "does not exist" would turn the id in the URL into a
    probe that confirms which papers other people have.
    """


class ConflictError(RepositoryError):
    """The write cannot proceed without destroying something.

    Raised, for instance, when deleting a paper that a saved literature
    review was generated from - see the ON DELETE RESTRICT in migration
    002, which exists so a review cannot silently come to claim more
    sources than it can still name.
    """


class PaperRepository(ABC):
    """Everything the library API needs from durable storage."""

    @abstractmethod
    async def health(self) -> bool:
        """Whether storage is reachable right now. Never raises."""

    # ---------- papers ----------

    @abstractmethod
    async def save_paper(self, request: SavePaperRequest) -> PaperDetail:
        """Persist a paper and its analysis, returning the stored record."""

    @abstractmethod
    async def list_papers(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        sort: SortOrder = SortOrder.NEWEST,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperListItem], int]:
        """Return one page of the library, plus the total match count.

        The total is what lets the UI say "12 of 40" honestly; deriving
        it from the page length would under-report on every page but the
        last.
        """

    @abstractmethod
    async def get_paper(self, paper_id: str) -> PaperDetail:
        """Return one paper with its most recent analysis.

        Raises `NotFoundError` when it does not exist.
        """

    @abstractmethod
    async def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper and its analyses. Raises `NotFoundError` if absent."""

    @abstractmethod
    async def get_papers_for_review(self, paper_ids: list[str]) -> list[PaperDetail]:
        """Fetch several papers for a cross-paper review.

        Raises `NotFoundError` if any requested id is missing, rather
        than quietly returning fewer: a review that claims five sources
        must not be built from four.
        """

    # ---------- literature reviews ----------

    @abstractmethod
    async def save_review(
        self,
        *,
        title: str,
        model_used: str,
        content: LiteratureReview,
        paper_ids: list[str],
    ) -> ReviewRecord:
        """Persist a literature review and its contributing papers."""

    @abstractmethod
    async def list_reviews(self, *, limit: int = 50) -> tuple[list[ReviewRecord], int]:
        """Return saved reviews, newest first."""

    @abstractmethod
    async def get_review(self, review_id: str) -> ReviewRecord:
        """Return one review. Raises `NotFoundError` when absent."""

    @abstractmethod
    async def delete_review(self, review_id: str) -> bool:
        """Delete a review and its paper links."""

    # ---------- dashboard ----------

    @abstractmethod
    async def stats(self) -> LibraryStats:
        """Real counts for the dashboard overview."""

    # ---------- global configuration ----------
    #
    # Reads are made with the caller's own token like everything else, so the
    # database decides what they may see and change. `set_active_provider` is
    # refused by RLS for a non-owner even if the API layer somehow let it
    # through - which is the point of putting the rule in the database.

    @abstractmethod
    async def is_owner(self, user_id: str) -> bool:
        """Whether this account may change global configuration.

        Never raises for "not an owner" - that is a normal answer, not an
        error. Raises only when the question could not be asked at all.
        """

    @abstractmethod
    async def get_active_provider(self, default: str) -> str:
        """The globally selected primary AI provider.

        `default` is returned when no row has been stored yet, so a deployment
        works before an owner has chosen anything.
        """

    @abstractmethod
    async def set_active_provider(self, provider: str, *, updated_by: str) -> None:
        """Store the globally selected primary AI provider."""
