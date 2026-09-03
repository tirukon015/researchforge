"""Signed-in callers for the test suite. NO NETWORK, NO REAL ACCOUNTS.

WHY THIS EXISTS
---------------
Every route that touches research data now depends on `require_user`, which
normally asks Supabase to verify an access token. A test must not make that
call: it would need real credentials, a network, and a live project, and it
would test Supabase rather than this application.

So the dependency is overridden with a fixed identity. That is the point of
having it be a dependency at all.

WHAT THIS DOES NOT WEAKEN
-------------------------
Overriding `require_user` fakes only the *answer to "who is calling"*. The
isolation guarantee itself is enforced two layers down, by Row Level Security
in Postgres, and no test override can reach it. `tests/test_ownership.py`
tests the seam that IS this application's responsibility: that each caller's
identity is carried through to the database unchanged, and that one user's
request can never be served from another user's repository.

USER_A and USER_B are two different people with two different ids. They are
used together, in the same test, to assert that a request as one never returns
the other's rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from src.api.auth import AuthUser, reset_auth_cache
from src.main import app

# Obvious fakes. Valid UUID shapes because the real ids are UUIDs and a test
# that passed with "user-a" could hide a place that parses them.
USER_A = AuthUser(
    id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    email="user-a@example.test",
    full_name="User A",
    token="not-a-real-access-token-for-user-a",
)

USER_B = AuthUser(
    id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    email="user-b@example.test",
    full_name="User B",
    token="not-a-real-access-token-for-user-b",
)


def sign_in_as(user: AuthUser) -> None:
    """Make every subsequent request in this test arrive as `user`."""
    from src.api.auth import require_user

    app.dependency_overrides[require_user] = lambda: user


def sign_out() -> None:
    """Remove the identity override, so routes require a real token again.

    Used by the tests that assert an unauthenticated request is refused.
    """
    from src.api.auth import require_user

    app.dependency_overrides.pop(require_user, None)
    reset_auth_cache()


@contextmanager
def signed_in_as(user: AuthUser) -> Iterator[AuthUser]:
    """Scope an identity to a block, restoring whatever was there before."""
    from src.api.auth import require_user

    previous = app.dependency_overrides.get(require_user)
    sign_in_as(user)
    try:
        yield user
    finally:
        if previous is None:
            app.dependency_overrides.pop(require_user, None)
        else:
            app.dependency_overrides[require_user] = previous
