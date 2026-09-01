"""Research library storage.

Import `PaperRepository` and the error types from here. Never import a
concrete implementation outside `get_repository`: that would couple the API to
one database vendor and defeat the abstraction, exactly as with
`src.rag.llm` and `src.rag.embeddings`.

The factory returns `None` rather than raising when storage is not configured.
An unconfigured library is a normal deployment state, not a fault: analysis
works perfectly well without one, so the API answers library requests with a
clear 503 and leaves everything else running.
"""

from src.config import Settings
from src.db.repository import (
    ConflictError,
    NotFoundError,
    PaperRepository,
    RepositoryError,
    RepositoryUnavailableError,
)

__all__ = [
    "ConflictError",
    "NotFoundError",
    "PaperRepository",
    "RepositoryError",
    "RepositoryUnavailableError",
    "get_repository",
]


def get_repository(settings: Settings) -> PaperRepository | None:
    """Build the configured repository, or `None` when there is none.

    The import is local so a deployment without a database never pays for the
    driver import, and so a future second backend does not force every caller
    to import every driver.
    """
    if not settings.has_database:
        return None

    from src.db.supabase import SupabaseRepository

    return SupabaseRepository(settings)
