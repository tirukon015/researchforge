"""Application configuration.

WHY THIS FILE EXISTS
--------------------
Every setting the app needs (ports, URLs, and later API keys) is read from
*environment variables* — never hard-coded. This gives us three things:

1. **Security.** Secrets live in a local `.env` file that Git ignores, so a key
   can never be committed by accident.
2. **Portability.** The same code runs on your Mac, on Windows, and on the
   deployment server. Only the environment changes.
3. **Safety.** Pydantic validates every value at startup. If something is
   missing or malformed, the app fails immediately with a clear message
   instead of crashing mysteriously later.

HOW IT WORKS
------------
`pydantic-settings` reads, in order of priority:
    1. real environment variables (used in production/deployment)
    2. the local `.env` file (used during development)
    3. the defaults written below
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = the folder containing this file's parent (src/ -> project root).
# Built with pathlib so it works identically on macOS, Windows, and Linux.
# NEVER hard-code an absolute path like "/Users/apple/..." here.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All application settings, validated at startup."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Ignore variables in .env that this class doesn't define yet
        # (e.g. the frontend's NEXT_PUBLIC_* values).
        extra="ignore",
    )

    # ---------- Application ----------
    app_name: str = "AI Research Paper Assistant"
    app_env: str = "development"
    debug: bool = True
    backend_port: int = 8000

    # ---------- Security ----------
    # Which website addresses are allowed to call this API.
    # Comma-separated in .env, e.g. "http://localhost:3000,https://myapp.vercel.app"
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated CORS setting into a clean list."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    # NOTE: AI provider, embedding model, and database settings are deliberately
    # NOT defined yet. Those decisions (D5, D6) are still open — see
    # PROJECT_PLAN.md §F. They will be added in the milestone that needs them.


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loaded once and cached.

    `@lru_cache` means the `.env` file is read a single time rather than on
    every request. FastAPI calls this via dependency injection, which also
    makes settings easy to override in tests.
    """
    return Settings()
