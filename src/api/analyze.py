"""POST /api/analyze - upload a research paper and get it analysed.

ERROR MAPPING
-------------
Status codes are chosen so the frontend can tell the three cases apart without
parsing message text:

    413  the file is too large
    422  the upload is not a usable PDF (wrong type, empty, scanned, encrypted)
    429  the AI provider is rate limiting, or its quota is spent. Carries
         Retry-After when the provider said how long to wait, and is kept
         DISTINCT from 502: "you are over your allowance" is not "the service
         is broken", and only one of the two is worth retrying
    502  the AI service replied with something unusable, or failed
    503  the server has no API key configured - an operator problem, not the
         user's fault, and the only one where retrying identically will help
         once someone fixes the deployment

Anything that is the uploader's fault is a 4xx and carries a message written
for them. Nothing here returns a 500 for an expected condition.
"""

import logging
import math

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.auth import AuthUser, require_user
from src.config import Settings, get_settings
from src.db import PaperRepository, RepositoryError, get_repository
from src.ingestion.pdf import PdfExtractionError
from src.rag.llm import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
    build_routed_provider,
)
from src.schemas.analysis import AnalysisResponse
from src.services.analysis import analyse_paper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Analysis"])


def rate_limit_headers(exc: LLMRateLimitError) -> dict[str, str]:
    """Response headers describing a rate limit, carrying no configuration.

    `Retry-After` is set only when the provider actually supplied a delay:
    inventing one would have the client count down to a moment we have no
    reason to think is right. `X-Quota-Exhausted` separates "wait a moment"
    from "this allowance is spent", which the interface words differently.

    Both values are derived from the provider's reply. Neither exposes the API
    key, the model, or any environment variable.
    """
    headers: dict[str, str] = {}
    if exc.retry_after_seconds is not None:
        # Retry-After is defined in whole seconds; round up so the client never
        # retries a fraction of a second early.
        headers["Retry-After"] = str(max(1, math.ceil(exc.retry_after_seconds)))
    if exc.quota_exhausted:
        headers["X-Quota-Exhausted"] = "true"
    return headers


def get_optional_library(
    user: AuthUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> PaperRepository | None:
    """The library, or None when this deployment has no database.

    Deliberately different from `get_library`, which answers 503. Analysis is
    genuinely useful with nowhere to save the result, so the analysis path must
    not require storage - it only wants to ASK storage which provider the owner
    chose, and it has a sensible answer when there is nobody to ask.
    """
    if not settings.has_database:
        return None
    try:
        return get_repository(settings, access_token=user.token, user_id=user.id)
    except RepositoryError:
        return None


async def get_provider(
    settings: Settings = Depends(get_settings),
    library: PaperRepository | None = Depends(get_optional_library),
) -> LLMProvider:
    """Build the OWNER'S chosen provider, with the other one as fallback.

    The primary comes from the database (`system_settings.active_ai_provider`),
    so changing it is a setting rather than a redeploy. `settings.llm_provider`
    is only the starting value for a deployment where nobody has chosen yet.

    A NEW ROUTER PER REQUEST, on purpose: it remembers whether it has already
    failed over, and that per-instance memory is what limits one analysis to a
    single change of model (see src/rag/llm/router.py).

    Being a dependency rather than a direct call is what makes the endpoint
    testable: the suite overrides this with an offline fake, so no test ever
    needs a network connection or spends a token.
    """
    active = settings.llm_provider_name
    if library is not None:
        try:
            active = await library.get_active_provider(active)
        except RepositoryError as exc:
            # An unreadable setting must not take analysis down. Fall back to
            # the deployment default and say so in the log, not to the user.
            logger.warning("could not read the active AI provider: %s", exc)

    try:
        return build_routed_provider(active, settings)
    except LLMCredentialsError as exc:
        # A missing key is an operator problem, not the uploader's. The message
        # names the missing variable but never its value.
        logger.error("analysis unavailable: no LLM credentials configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Analyse a research paper",
    responses={
        401: {"description": "Not signed in, or the session expired"},
        413: {"description": "File exceeds the upload size limit"},
        422: {"description": "The file is not a readable PDF"},
        429: {"description": "The AI provider is rate limiting or its quota is spent"},
        502: {"description": "The AI service failed or returned unusable output"},
        503: {"description": "No AI credentials are configured on the server"},
    },
)
async def analyze(
    # ORDER MATTERS. FastAPI resolves dependencies top to bottom and stops at
    # the first failure, so `require_user` is declared FIRST: an anonymous
    # caller is turned away before the server reveals anything about its own
    # configuration (a missing API key used to answer 503 here, telling a
    # stranger which credential the deployment lacks) and before it reads a
    # 25 MB upload it has already decided to refuse.
    user: AuthUser = Depends(require_user),
    file: UploadFile = File(..., description="The research paper, as a PDF."),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_provider),
) -> AnalysisResponse:
    """Extract text from an uploaded paper and produce a summary, research gap
    analysis, and literature review - all grounded in the paper's own content.

    Sign-in is required even though this route stores nothing. Each call is
    three reasoning passes against a rate-limited, paid quota, and an open
    endpoint would let anyone spend the project's allowance - which is a denial
    of service for the people who actually have accounts. `user` is not
    otherwise read: the result is returned to the caller and saved only if they
    then choose to keep it.
    """
    # Read once. Size is checked against the real byte count rather than the
    # client-supplied content-length header, which cannot be trusted.
    data = await file.read()

    if len(data) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"This file is {len(data) / 1_048_576:.1f} MB, which is over "
                f"the {settings.max_upload_size_mb} MB limit."
            ),
        )

    filename = file.filename or "upload.pdf"

    # The declared content type is a hint only - `extract_document` verifies the
    # actual PDF signature, so a mislabelled file still cannot get through.
    if file.content_type and file.content_type not in settings.allowed_file_types_list:
        logger.info("upload declared content-type %s", file.content_type)

    try:
        return analyse_paper(data=data, filename=filename, provider=provider, settings=settings)
    except PdfExtractionError as exc:
        logger.info("rejected upload %s: %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except LLMCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LLMRateLimitError as exc:
        # Caught BEFORE LLMError, which it subclasses. Reported as 429 so the
        # client can tell a quota problem from a broken upstream and can stop
        # inviting the user to retry into a limit that is already spent.
        logger.warning("rate limited analysing %s (exhausted=%s)", filename, exc.quota_exhausted)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers=rate_limit_headers(exc),
        ) from exc
    except LLMResponseError as exc:
        logger.warning("unusable model output for %s: %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except LLMError as exc:
        logger.warning("generation failed for %s: %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
