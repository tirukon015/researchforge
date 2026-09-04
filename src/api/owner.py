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


class ProviderState(BaseModel):
    """One provider, as the availability controls need to render it."""

    key: str
    label: str
    model: str
    enabled: bool
    is_primary: bool
    # Whether the server has an API key for it. A provider can be enabled and
    # still unusable, and the interface should say so rather than implying a
    # standby that cannot run.
    has_credentials: bool


class AiConfig(BaseModel):
    """The global AI configuration, as the interface needs to render it."""

    active_provider: str
    active_provider_label: str
    # Always the opposite provider. Sent by the server rather than computed in
    # the browser so there is ONE definition of "the fallback", and the UI
    # cannot drift out of step with the router.
    fallback_provider: str
    fallback_provider_label: str
    # Whether the fallback will ACTUALLY run: it needs a key AND the owner's
    # permission. False when the owner has switched it off, which is not a
    # fault - it is what they asked for.
    fallback_available: bool
    # Which providers this deployment could switch to right now.
    available_providers: list[str]
    # Availability, and everything the controls need to render themselves.
    enabled_providers: list[str]
    providers: list[ProviderState]


class AiConfigUpdate(BaseModel):
    """A change to the global configuration. Both fields are optional, but at
    least one must be present - and the RESULTING state is validated as a
    whole, so "switch primary and disable the old one" is one atomic request
    rather than two that could leave an invalid state in between."""

    provider: str | None = Field(default=None, description="anthropic or groq")
    enabled: list[str] | None = Field(
        default=None,
        description="Providers the owner permits. Must not be empty.",
    )


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


def _model_for(provider: str, settings: Settings) -> str:
    """The model this provider would use. Shown so the owner is switching a
    named model on and off, not an abstraction."""
    return {
        "anthropic": settings.model_for_provider("anthropic", settings.anthropic_model),
        "groq": settings.model_for_provider("groq", settings.groq_model),
    }.get(provider, "")


def _config(provider: str, enabled: list[str], settings: Settings) -> AiConfig:
    fallback = OPPOSITE[provider]
    permitted = {p.strip().lower() for p in enabled}
    return AiConfig(
        active_provider=provider,
        active_provider_label=display_name(provider),
        fallback_provider=fallback,
        fallback_provider_label=display_name(fallback),
        # A fallback needs BOTH a key and the owner's permission. Reporting it
        # as available when the owner switched it off would describe a standby
        # the router will never call.
        fallback_available=(fallback in permitted and settings.has_credentials_for(fallback)),
        available_providers=list(PROVIDERS),
        enabled_providers=sorted(permitted),
        providers=[
            ProviderState(
                key=key,
                label=display_name(key),
                model=_model_for(key, settings),
                enabled=key in permitted,
                is_primary=key == provider,
                has_credentials=settings.has_credentials_for(key),
            )
            for key in PROVIDERS
        ],
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
        enabled = await library.get_enabled_providers(list(PROVIDERS))
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return _config(provider, enabled, settings)


@router.put(
    "/ai-config",
    response_model=AiConfig,
    summary="Choose the global primary AI provider and which providers are enabled",
    responses={
        403: {"description": "Not the owner"},
        422: {
            "description": (
                "Unsupported provider, an empty enabled set, or an attempt to "
                "disable the current primary"
            )
        },
    },
)
async def set_ai_config(
    request: AiConfigUpdate,
    user: AuthUser = Depends(require_owner),
    library: PaperRepository = Depends(get_library),
    settings: Settings = Depends(get_settings),
) -> AiConfig:
    """Set the primary provider, which providers are enabled, or both.

    Affects NEW analyses only. Stored analyses keep the provider that actually
    produced them - rewriting that would destroy the record of what happened.

    THE RESULTING STATE IS VALIDATED AS A WHOLE, not each field on its own.
    That is what makes "make Claude primary and switch Groq off" a single
    atomic request: validating field by field would reject it, because each
    change is invalid until the other one is applied. It also means the two
    invariants below are checked against what the configuration WILL be rather
    than what it currently is.
    """
    if request.provider is None and request.enabled is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nothing to change. Send a primary provider, an enabled list, or both.",
        )

    try:
        current_provider = await library.get_active_provider(settings.llm_provider_name)
        current_enabled = await library.get_enabled_providers(list(PROVIDERS))
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    # ---- what the configuration would become ----
    provider = current_provider
    if request.provider is not None:
        provider = request.provider.strip().lower()
        if provider not in PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"{request.provider!r} is not a provider this application "
                    f"supports. Choose {' or '.join(PROVIDERS)}."
                ),
            )

    enabled = list(current_enabled)
    if request.enabled is not None:
        enabled = sorted({p.strip().lower() for p in request.enabled if p and p.strip()})
        unknown = [p for p in enabled if p not in PROVIDERS]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"{unknown[0]!r} is not a provider this application supports. "
                    f"Choose from {' and '.join(PROVIDERS)}."
                ),
            )

    # ---- INVARIANT 1: something must be able to run ----
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "At least one AI provider must stay enabled. With both switched "
                "off, no paper could be analysed."
            ),
        )

    # ---- INVARIANT 2: the primary must be one of the enabled ones ----
    #
    # This is the rule that stops an owner disabling the provider currently
    # doing the work. The message names the fix rather than just refusing,
    # because "you cannot do that" without "here is what to do instead" is the
    # more annoying half of a validation error.
    if provider not in enabled:
        other = OPPOSITE[provider]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{display_name(provider)} is the primary provider, so it cannot "
                f"be switched off. Make {display_name(other)} the primary first, "
                f"then disable {display_name(provider)}."
            ),
        )

    # ---- write only what actually changed ----
    try:
        if provider != current_provider:
            await library.set_active_provider(provider, updated_by=user.id)
        if enabled != sorted(current_enabled):
            await library.set_enabled_providers(enabled, updated_by=user.id)
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    logger.info("AI configuration: primary=%s enabled=%s", provider, ",".join(enabled))
    return _config(provider, enabled, settings)
