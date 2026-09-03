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
    AuthExpiredError,
    ConflictError,
    NotFoundError,
    PaperRepository,
    RepositoryError,
    RepositoryUnavailableError,
)

__all__ = [
    "AuthExpiredError",
    "ConflictError",
    "NotFoundError",
    "PaperRepository",
    "RepositoryError",
    "RepositoryUnavailableError",
    "get_repository",
]


def get_repository(
    settings: Settings,
    access_token: str,
    user_id: str,
) -> PaperRepository | None:
    """Build the configured repository FOR ONE USER, or `None` when there is none.

    A repository is always scoped to a person. `access_token` is that person's
    Supabase JWT, sent on every database request so Row Level Security resolves
    `auth.uid()` to them, and `user_id` is stamped onto rows they create.

    Both are required arguments rather than optional ones. An "unscoped"
    repository is not a thing this application should be able to construct by
    forgetting an argument: that object would read the whole library, and the
    reason this signature changed is that it used to.

    The import is local so a deployment without a database never pays for the
    driver import, and so a future second backend does not force every caller
    to import every driver.
    """
    if not settings.has_database:
        return None

    from src.db.supabase import SupabaseRepository

    return SupabaseRepository(settings, access_token=access_token, user_id=user_id)
