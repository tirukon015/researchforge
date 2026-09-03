"""Application configuration.

WHY THIS FILE EXISTS
--------------------
Every setting the app needs (ports, URLs, and later API keys) is read from
*environment variables*, never hard-coded. This gives us three things:

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


# Which model names belong to which provider. Used to spot an LLM_MODEL left
# over from a different vendor - see Settings.model_for_provider. Kept at module
# level rather than on the class because a pydantic-settings model turns
# annotated attributes into fields.
MODEL_PREFIXES_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "anthropic": ("claude",),
    "gemini": ("gemini",),
}


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
    app_name: str = "ResearchForge"
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

    # ---------- Embedding model (LOCKED, decision D6) ----------
    # Jina jina-embeddings-v3 @ 1024 dimensions.
    #
    # ⚠️ embedding_dimensions is PERMANENT. It must match the vector(1024)
    # column in the database exactly. Changing it means re-embedding every
    # paper. See PROJECT_PLAN.md §F decision 2.
    embedding_provider: str = "jina"
    embedding_model: str = "jina-embeddings-v3"
    embedding_dimensions: int = 1024

    # The API key. Empty by default so the app still starts without it,
    # only the embedding feature fails, and with a clear message.
    # NEVER hard-code a key here; it comes from .env or the host environment.
    jina_api_key: str = ""

    @property
    def has_embedding_credentials(self) -> bool:
        """Whether an embedding API key is configured."""
        return bool(self.jina_api_key.strip())

    # ---------- LLM (generation) ----------
    # D5 is still formally OPEN. Rather than hard-wiring a vendor, the code
    # talks to `src.rag.llm.base.LLMProvider`, and `llm_provider` selects the
    # concrete implementation. Switching vendors is a new file plus this one
    # env var - never a rewrite. Two are implemented: "anthropic" and "gemini".
    #
    # Gemini is the default because it is what the deployment runs on. The
    # defaults are kept in step: llm_model names a Gemini model, and
    # model_for_provider ignores a name belonging to the other vendor, so
    # changing llm_provider alone still produces a working configuration.
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.7-flash"

    # Effort controls how hard the model thinks. "high" is the sensible
    # default for analytical work; "low" is enough for smoke tests.
    llm_effort: str = "high"
    llm_max_output_tokens: int = 16000

    # Server-side only. Empty by default so the app still starts without it -
    # only the /api/analyze endpoint fails, and with a clear message.
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    @property
    def llm_provider_name(self) -> str:
        """The selected provider, normalised once so callers agree on the key."""
        return self.llm_provider.strip().lower()

    @property
    def has_llm_credentials(self) -> bool:
        """Whether a generation API key is configured FOR THE SELECTED provider.

        Provider-aware on purpose: with two vendors wired up, an Anthropic key
        left in the environment would otherwise report the app as ready to run
        on Gemini, and the failure would surface as a confusing 502 mid-analysis
        instead of an honest 503 up front.
        """
        return bool(self.llm_api_key.strip())

    @property
    def llm_api_key(self) -> str:
        """The API key belonging to the selected provider ("" if none/unknown).

        Never logged and never returned by an endpoint - callers pass it
        straight to the provider constructor.
        """
        return {
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
        }.get(self.llm_provider_name, "")

    def model_for_provider(self, provider: str, default: str) -> str:
        """Return `llm_model` if it belongs to `provider`, else `default`.

        LLM_MODEL is deliberately one setting shared by every provider, because
        a paper is analysed by one model at a time. The cost is that a value
        left over from another vendor ("claude-opus-5" with LLM_PROVIDER=gemini)
        would be sent verbatim and rejected as an unknown model. This resolves
        that: an inherited model name gives way to the provider's own default,
        so switching vendors really is one variable.
        """
        configured = self.llm_model.strip()
        prefixes = MODEL_PREFIXES_BY_PROVIDER.get(provider, ())
        if configured and (not prefixes or configured.lower().startswith(prefixes)):
            return configured
        return default

    # ---------- Database (Supabase) ----------
    # Empty by default so the API still starts and analysis still works
    # without a database. The library endpoints then answer with a clear
    # "not configured" rather than the whole app refusing to boot -
    # analysis is genuinely useful on its own.
    #
    # SECURITY: the service-role key bypasses Row Level Security. It is
    # read here, server-side only, and must NEVER be given a NEXT_PUBLIC_
    # prefix or returned by any endpoint.
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    storage_bucket: str = "papers"

    # The PUBLIC key. Safe to ship in a browser and safe to log; it is listed
    # here because the backend needs it for two things that are not writes:
    #
    #   1. `apikey` on every PostgREST request. PostgREST requires the header
    #      to route the request to the project at all, and pairing it with the
    #      caller's own JWT in `Authorization` is what makes Row Level Security
    #      evaluate `auth.uid()` as THE SIGNED-IN USER rather than as NULL.
    #   2. Calling GoTrue's /auth/v1/user to turn an access token into an
    #      identity, which is how a request is authenticated.
    #
    # It is deliberately NOT the service-role key. Reading the library through
    # the user's own token means the DATABASE enforces ownership; a service key
    # bypasses RLS, which would leave isolation resting on the application
    # remembering a WHERE clause on every query it will ever have.
    supabase_anon_key: str = ""

    @property
    def has_auth(self) -> bool:
        """Whether Supabase authentication is configured.

        Needs the URL and the public key, and nothing else: the secret key
        plays no part in authenticating a user. Reported separately from
        `has_database` so a deployment missing only this says so, instead of
        answering 401 to every request with no explanation.
        """
        return bool(self.supabase_url.strip() and self.supabase_anon_key.strip())

    @property
    def supabase_auth_url(self) -> str:
        """Base URL of the GoTrue (auth) API, without a trailing slash."""
        return f"{self.supabase_url.strip().rstrip('/')}/auth/v1"

    @property
    def supabase_key_is_publishable(self) -> bool:
        """Whether the configured key is a PUBLIC one in a private slot.

        Supabase issues two kinds of key. The publishable one
        (`sb_publishable_...`) is designed to ship inside a browser bundle and
        is subject to Row Level Security. The secret one (`sb_secret_...`, or a
        legacy `service_role` JWT) bypasses RLS and is what a trusted backend
        needs.

        Putting the publishable key in this variable does not fail loudly, and
        that is exactly why it is worth detecting. Migration 002 enables RLS
        with `user_id = auth.uid()` policies, and `auth.uid()` is NULL for an
        anonymous key, so:

          - every SELECT succeeds with HTTP 200 and returns ZERO ROWS
          - every INSERT is refused

        The reads are the dangerous half. Nothing errors, so the dashboard
        renders "0 papers" and "0 research gaps" as though they were measured
        facts about an empty library, when the truth is that the server cannot
        see its own data. A wrong number stated confidently is worse than an
        error, so this is caught here and reported as a misconfiguration.
        """
        return self.supabase_service_role_key.strip().startswith("sb_publishable_")

    @property
    def has_database(self) -> bool:
        """Whether durable storage is configured AND usable.

        Both halves of the pair are required: a URL without a key cannot
        authenticate, and a key without a URL has nowhere to go. Reporting
        "configured" on half a pair would turn a clear 503 into a confusing
        timeout.

        A publishable key counts as NOT configured. It would technically
        connect, which is the problem: it would connect and then quietly show
        an empty library. Refusing it means the interface says "not connected",
        which is true, instead of "you have no papers", which is not.
        """
        if self.supabase_key_is_publishable:
            return False
        return bool(self.supabase_url.strip() and self.supabase_service_role_key.strip())

    @property
    def supabase_rest_url(self) -> str:
        """Base URL of the PostgREST API, without a trailing slash."""
        return f"{self.supabase_url.strip().rstrip('/')}/rest/v1"

    @property
    def supabase_storage_url(self) -> str:
        return f"{self.supabase_url.strip().rstrip('/')}/storage/v1"

    # ---------- Upload limits ----------
    max_upload_size_mb: int = 25
    allowed_file_types: str = "application/pdf"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_file_types_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_file_types.split(",") if t.strip()]

    # ---------- Long-paper handling ----------
    # Claude Opus 5 has a 1,000,000-token context window, so an ordinary paper
    # (5k-60k tokens) fits whole and chunking would only lose cross-section
    # context. Chunking therefore ACTIVATES ONLY above this threshold, where
    # sending everything really would be unsafe. Measured in characters
    # because that needs no tokeniser dependency; ~4 chars per token is the
    # usual English approximation, so 400k chars is roughly 100k tokens - a
    # deliberately conservative fraction of the window.
    long_paper_char_threshold: int = 400_000
    # Named `long_paper_*` deliberately: CHUNK_SIZE / CHUNK_OVERLAP in
    # .env.example belong to the future RAG embedding chunker, which splits
    # text into ~1,000-char pieces. Reusing those names here would make one
    # setting silently drive two unrelated chunkers - and a 1,000-char
    # long-paper chunk would fire hundreds of LLM calls per upload.
    long_paper_chunk_size: int = 40_000
    long_paper_chunk_overlap: int = 2_000

    # NOTE: database settings are deliberately NOT defined yet. They are added
    # in the milestone that needs them (Milestone 2).


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loaded once and cached.

    `@lru_cache` means the `.env` file is read a single time rather than on
    every request. FastAPI calls this via dependency injection, which also
    makes settings easy to override in tests.
    """
    return Settings()
