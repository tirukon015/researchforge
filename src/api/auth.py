"""Who is calling: turning a Supabase access token into an identity.

WHAT AUTHENTICATION IS FOR HERE
-------------------------------
Before this module existed, `GET /api/papers` returned every paper in the
database to anybody who asked. There was one library and everyone shared it.
Authentication is what makes "your library" a true phrase.

HOW A REQUEST PROVES WHO IT IS
------------------------------
The browser signs in with Supabase directly (email + password) and receives an
**access token**: a short-lived JWT that Supabase signed. Every call to this
API then carries it::

    Authorization: Bearer eyJhbGciOi...

This module reads that header and asks Supabase whether the token is real.

WHY IT ASKS SUPABASE INSTEAD OF VERIFYING THE SIGNATURE LOCALLY
---------------------------------------------------------------
Verifying locally would need the project's JWT signing secret in this
deployment's environment, plus a JWT library, plus code that has to keep pace
with Supabase's move to asymmetric signing keys. Calling GoTrue's ``/user``
endpoint needs neither: it is the same check Supabase itself performs, it
honours revocation and sign-out immediately (a locally verified token stays
"valid" until it expires, even after the user logs out), and it returns the
profile the interface wants to display anyway.

The cost is one HTTP call. `_CACHE` removes it for repeat requests inside a
short window, which is what a page load's burst of calls actually looks like.

WHAT THIS MODULE DOES **NOT** DO
--------------------------------
It does not authorise anything. Knowing who is calling is not the same as
deciding what they may see, and this file deliberately makes no such decision.
Ownership is enforced by Row Level Security in the database, reached by handing
PostgREST the caller's own token (see `src/db/supabase.py`). If this module were
ever bypassed, the database would still refuse to show one user another user's
rows - which is the property that makes the isolation claim worth making.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException, status

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

# How long a verified token is trusted without re-asking Supabase.
#
# THIS IS THE WINDOW IN WHICH A SIGNED-OUT TOKEN STILL WORKS, so it is stated
# as a bound rather than described as "immediate".
#
# It was 30 seconds, and a live logout test caught what that actually means: a
# token used just before signing out kept working for the rest of the window.
# For a logout on a shared computer that is too long - "log out" has to mean it.
#
# Five seconds is the smallest value that still does the job the cache exists
# for. One page load fires several API calls within about a second, so this
# collapses that burst into a single verification while bounding post-logout
# validity to roughly the time it takes to close the tab.
#
# It cannot be driven to zero without giving up the cache entirely, and it
# cannot be fixed by evicting on sign-out either: the API runs as several
# serverless instances, so evicting on the one that handled the request would
# leave the others still holding it - a fix that LOOKS complete and is racy.
# A small, measured, documented bound is the honest answer.
_CACHE_TTL_SECONDS = 5.0

# Bounded so a flood of distinct tokens cannot grow this without limit. The
# cache is a latency optimisation, never a source of truth, so evicting the
# whole thing when it fills is correct and costs one extra round trip.
_CACHE_MAX_ENTRIES = 512

_CACHE: dict[str, tuple[float, AuthUser]] = {}


AUTH_NOT_CONFIGURED = (
    "Accounts are not available on this deployment. SUPABASE_URL and "
    "SUPABASE_ANON_KEY must be set on the server."
)

NOT_SIGNED_IN = "You are not signed in. Please sign in and try again."

SESSION_EXPIRED = "Your session has expired. Please sign in again."


@dataclass(frozen=True)
class AuthUser:
    """The signed-in caller.

    `token` is carried along because the data layer needs it: the library is
    read with the USER'S OWN credentials so Postgres evaluates `auth.uid()` to
    this person and Row Level Security does the filtering. Passing the identity
    without the token would force the repository back onto a service key that
    bypasses RLS.
    """

    id: str
    email: str
    full_name: str
    token: str


def _clear_expired(now: float) -> None:
    for key, (expires_at, _) in list(_CACHE.items()):
        if expires_at <= now:
            del _CACHE[key]


def reset_auth_cache() -> None:
    """Empty the verification cache.

    Exists for the test suite, which must not have one test's fake token
    answer another test's request.
    """
    _CACHE.clear()


def _display_name(payload: dict) -> str:
    """Pick the best available human name, falling back to the email.

    Supabase keeps whatever the sign-up form supplied in `user_metadata`. The
    frontend sends `full_name`; `name` is checked too because the Supabase
    dashboard and third-party providers use that key, and an account created
    outside our form should still show a name rather than a blank.
    """
    metadata = payload.get("user_metadata") or {}
    for key in ("full_name", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(payload.get("email") or "")


async def verify_token(token: str, settings: Settings) -> AuthUser:
    """Resolve an access token to a user, or raise 401.

    Raises `HTTPException` rather than returning None so every caller fails the
    same way: there is no code path where an unverified token quietly becomes
    an anonymous request that then reads something.
    """
    if not settings.has_auth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=AUTH_NOT_CONFIGURED
        )

    now = time.monotonic()
    cached = _CACHE.get(token)
    if cached is not None and cached[0] > now:
        return cached[1]

    anon_key = settings.supabase_anon_key.strip()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.supabase_auth_url}/user",
                headers={"apikey": anon_key, "Authorization": f"Bearer {token}"},
            )
    except httpx.TimeoutException as exc:
        # 503, not 401. A slow auth service is not a rejected credential, and
        # telling the user to sign in again would send them to a form that is
        # equally unable to respond.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The sign-in service did not respond in time. Please try again.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach the sign-in service. Please try again.",
        ) from exc

    if response.status_code in (401, 403):
        # The single most common cause is an access token that aged out, which
        # is normal and not an error the user did anything to cause. The
        # frontend refreshes silently first and only shows this if that failed.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_EXPIRED)
    if not response.is_success:
        logger.warning("auth verification failed: HTTP %s", response.status_code)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The sign-in service could not confirm your account. Please try again.",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The sign-in service returned an unreadable response.",
        ) from exc

    user_id = str(payload.get("id") or "")
    if not user_id:
        # A 200 with no id is a contract violation, not a credential problem.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The sign-in service returned an account with no identifier.",
        )

    user = AuthUser(
        id=user_id,
        email=str(payload.get("email") or ""),
        full_name=_display_name(payload),
        token=token,
    )

    if len(_CACHE) >= _CACHE_MAX_ENTRIES:
        _clear_expired(now)
        if len(_CACHE) >= _CACHE_MAX_ENTRIES:
            _CACHE.clear()
    _CACHE[token] = (now + _CACHE_TTL_SECONDS, user)
    return user


def bearer_token(authorization: str | None) -> str | None:
    """Pull the token out of an Authorization header, or None."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = value.strip()
    return token or None


async def require_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    """FastAPI dependency: the signed-in caller, or 401.

    Put this on every route that touches a person's research data. A route
    without it is a route that serves the library to the internet, which is
    exactly the fault this replaced.
    """
    token = bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_SIGNED_IN,
            # Named so a client can tell "you never sent a credential" apart
            # from "the one you sent was refused" without parsing prose.
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await verify_token(token, settings)
