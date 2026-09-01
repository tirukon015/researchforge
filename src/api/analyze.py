"""POST /api/analyze - upload a research paper and get it analysed.

ERROR MAPPING
-------------
Status codes are chosen so the frontend can tell the three cases apart without
parsing message text:

    413  the file is too large
    422  the upload is not a usable PDF (wrong type, empty, scanned, encrypted)
    502  the AI service replied with something unusable, or failed
    503  the server has no API key configured - an operator problem, not the
         user's fault, and the only one where retrying identically will help
         once someone fixes the deployment

Anything that is the uploader's fault is a 4xx and carries a message written
for them. Nothing here returns a 500 for an expected condition.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.config import Settings, get_settings
from src.ingestion.pdf import PdfExtractionError
from src.rag.llm import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMResponseError,
    get_llm_provider,
)
from src.schemas.analysis import AnalysisResponse
from src.services.analysis import analyse_paper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Analysis"])


def get_provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    """Build the configured LLM provider as a FastAPI dependency.

    Being a dependency rather than a direct call is what makes the endpoint
    testable: the suite overrides this with an offline fake, so no test ever
    needs a network connection or spends a token.
    """
    try:
        return get_llm_provider(settings)
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
        413: {"description": "File exceeds the upload size limit"},
        422: {"description": "The file is not a readable PDF"},
        502: {"description": "The AI service failed or returned unusable output"},
        503: {"description": "No AI credentials are configured on the server"},
    },
)
async def analyze(
    file: UploadFile = File(..., description="The research paper, as a PDF."),
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_provider),
) -> AnalysisResponse:
    """Extract text from an uploaded paper and produce a summary, research gap
    analysis, and literature review - all grounded in the paper's own content.
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
    except LLMResponseError as exc:
        logger.warning("unusable model output for %s: %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except LLMError as exc:
        logger.warning("generation failed for %s: %s", filename, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
