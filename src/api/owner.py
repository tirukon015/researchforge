"""Owner-only global configuration: which AI provider is primary.

WHAT "OWNER" MEANS HERE
-----------------------
One account (or a small named set) that may change configuration affecting
every user. Ordinary users cannot see these controls and cannot call these
endpoints.

HOW OWNERSHIP IS DECIDED, AND WHY IT IS NOT AN EMAIL CHECK IN THE UI
--------------------------------------------------------------------
Two independent sources, checked server-side:

  1. a row in the `app_owners` table (the durable answer, and the one the
     database's own policies enforce), or
  2. the caller's email matching `OWNER_EMAIL` in the server environment.

(2) exists because `app_owners` starts empty and somebody has to grant the
first owner. It is safe because the email is read from a token **Supabase has
already verified**, never from anything the browser sent us.

What ownership is emphatically NOT is a comparison performed in the frontend.
Hiding a button stops nobody: the endpoints below are what actually refuse, and
underneath them the RLS policies from migration 004 refuse again. A normal user
who calls this API directly gets 403; a normal user who tries to write the row
straight through PostgREST is refused by the database.

STATUS CODES
------------
    401  not signed in
    403  signed in, but not an owner
    503  the library is not connected, so there is nowhere to read/write config
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth import AuthUser, require_user
from src.api.papers import get_library
from src.config import Settings, get_settings
from src.db import PaperRepository, RepositoryError
from src.rag.llm.router import OPPOSITE, PROVIDERS, display_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/owner", tags=["Owner"])

NOT_OWNER = (
    "This setting can only be changed by the project owner. Your own research "
    "library is unaffected."
)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class AiConfig(BaseModel):
    """The global AI configuration, as the interface needs to render it."""

    active_provider: str
    active_provider_label: str
    # Always the opposite provider. Sent by the server rather than computed in
    # the browser so there is ONE definition of "the fallback", and the UI
    # cannot drift out of step with the router.
    fallback_provider: str
    fallback_provider_label: str
    # Whether the fallback could actually run. A fallback with no API key is
    # not a fallback, and the interface must not imply otherwise.
    fallback_available: bool
    # Which providers this deployment could switch to right now.
    available_providers: list[str]


class AiConfigUpdate(BaseModel):
    provider: str = Field(..., description="anthropic or groq")


class OwnerStatus(BaseModel):
    """Whether the caller may change global configuration."""

    is_owner: bool


# --------------------------------------------------------------------------- #
# Authorisation
# --------------------------------------------------------------------------- #


async def is_owner(user: AuthUser, library: PaperRepository, settings: Settings) -> bool:
    """Whether `user` may change global configuration.

    Never raises for a lookup failure: an unreachable owners table means we
    cannot prove ownership, and the safe answer to that is "no". Failing open
    here would grant global configuration to everyone during a database blip.
    """
    for email in settings.owner_emails:
        if user.email and user.email.strip().lower() == email:
            return True
    try:
        return await library.is_owner(user.id)
    except RepositoryError as exc:
        logger.warning("could not check ownership: %s", exc)
        return False


async def require_owner(
    user: AuthUser = Depends(require_user),
    library: PaperRepository = Depends(get_library),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    """Dependency: the caller, or 403.

    `require_user` runs first, so an anonymous caller gets 401 rather than 403.
    The two are different facts and the interface says different things about
    them: one means "sign in", the other means "this is not yours to change".
    """
    if not await is_owner(user, library, settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_OWNER)
    return user


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get(
    "/status",
    response_model=OwnerStatus,
    summary="Whether the signed-in user may change global AI configuration",
)
async def owner_status(
    user: AuthUser = Depends(require_user),
    library: PaperRepository = Depends(get_library),
    settings: Settings = Depends(get_settings),
) -> OwnerStatus:
    """Answers one boolean, for every signed-in user.

    Deliberately NOT behind `require_owner`: a normal user needs a truthful
    "no" so the Settings page can omit the section, and answering 403 here
    would make the ordinary case look like an error.
    """
    return OwnerStatus(is_owner=await is_owner(user, library, settings))


def _config(provider: str, settings: Settings) -> AiConfig:
    fallback = OPPOSITE[provider]
    return AiConfig(
        active_provider=provider,
        active_provider_label=display_name(provider),
        fallback_provider=fallback,
        fallback_provider_label=display_name(fallback),
        fallback_available=settings.has_credentials_for(fallback),
        available_providers=list(PROVIDERS),
    )


@router.get(
    "/ai-config",
    response_model=AiConfig,
    summary="The global primary AI provider, and its automatic fallback",
    responses={403: {"description": "Not the owner"}},
)
async def get_ai_config(
    _: AuthUser = Depends(require_owner),
    library: PaperRepository = Depends(get_library),
    settings: Settings = Depends(get_settings),
) -> AiConfig:
    try:
        provider = await library.get_active_provider(settings.llm_provider_name)
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return _config(provider, settings)


@router.put(
    "/ai-config",
    response_model=AiConfig,
    summary="Choose the global primary AI provider",
    responses={
        403: {"description": "Not the owner"},
        422: {"description": "Not a supported provider"},
    },
)
async def set_ai_config(
    request: AiConfigUpdate,
    user: AuthUser = Depends(require_owner),
    library: PaperRepository = Depends(get_library),
    settings: Settings = Depends(get_settings),
) -> AiConfig:
    """Set the primary provider. The other one becomes the fallback.

    Affects NEW analyses only. Stored analyses keep the provider that actually
    produced them - rewriting that would destroy the record of what happened.
    """
    provider = request.provider.strip().lower()
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{request.provider!r} is not a provider this application "
                f"supports. Choose {' or '.join(PROVIDERS)}."
            ),
        )

    try:
        await library.set_active_provider(provider, updated_by=user.id)
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    logger.info("active AI provider set to %s", provider)
    return _config(provider, settings)
