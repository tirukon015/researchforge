"""FastAPI application entry point.

MILESTONE 1 SCOPE
-----------------
This is deliberately minimal. It proves the backend foundation works:
the server starts, it reads configuration from the environment, it responds
to a request, and it is covered by a test.

No AI, no database, no RAG yet. Those arrive in later milestones.

RUN IT LOCALLY
--------------
    uvicorn src.main:app --reload --port 8000

Then open:
    http://localhost:8000/health   -> the health check
    http://localhost:8000/docs     -> interactive API documentation
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src import __version__
from src.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
# Declaring the shape of a response gives us two benefits for free:
#   1. FastAPI validates the output, so we can't accidentally return junk.
#   2. The /docs page documents it automatically.


class HealthResponse(BaseModel):
    """The payload returned by the health check endpoint."""

    status: str
    app_name: str
    version: str
    environment: str


class RootResponse(BaseModel):
    """A friendly landing payload describing the API."""

    message: str
    version: str
    docs_url: str
    health_url: str


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend API for ResearchForge, an AI Research Paper Assistant. "
        "Upload research papers, generate summaries, identify research gaps, "
        "and produce literature reviews — with citations back to the source."
    ),
    version=__version__,
    # Hide the interactive docs in production; they are a development tool.
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS: browsers block a web page from calling an API on a different address
# unless that API explicitly allows it. The frontend (localhost:3000) and this
# backend (localhost:8000) count as different addresses, so we allow it here.
# We use an explicit list, never "*", so the deployed API isn't open to everyone.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_model=RootResponse, tags=["System"])
def root() -> RootResponse:
    """Describe the API and point to the docs."""
    return RootResponse(
        message="ResearchForge API — AI Research Paper Assistant",
        version=__version__,
        docs_url="/docs",
        health_url="/health",
    )


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Report that the service is alive.

    Hosting platforms call this endpoint automatically to decide whether the
    service is healthy. It must stay fast and must never depend on an external
    service, or a slow database would make the whole app look "down".
    """
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
    )
