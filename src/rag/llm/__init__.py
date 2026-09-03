"""LLM providers.

Import `LLMProvider` and the error types from here. Never import a concrete
provider outside the factories below - that would couple the pipeline to one
vendor and defeat the abstraction (same rule as `src/rag/embeddings`).

ACTIVE PROVIDERS: `anthropic` and `groq`.

Gemini has been RETIRED from the active workflow. `gemini_provider.py` is kept
on disk because analyses produced by it are still in the database and the file
documents how they were made, but nothing routes to it: `build_provider` will
not construct one, and `active_ai_provider` cannot be set to it. Historical
`model_used` values are left exactly as they were recorded.
"""

from src.config import Settings
from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
)
from src.rag.llm.router import (
    DISPLAY_NAMES,
    OPPOSITE,
    PROVIDERS,
    RoutedLLMProvider,
    display_name,
    is_retryable,
)

__all__ = [
    "DISPLAY_NAMES",
    "LLMCredentialsError",
    "LLMError",
    "LLMProvider",
    "LLMRateLimitError",
    "LLMResponseError",
    "OPPOSITE",
    "PROVIDERS",
    "RoutedLLMProvider",
    "build_provider",
    "build_routed_provider",
    "display_name",
    "get_llm_provider",
    "is_retryable",
]


def build_provider(provider: str, settings: Settings) -> LLMProvider:
    """Build ONE concrete provider by name.

    The import is local so adding a provider never forces every caller to
    import every vendor SDK, and so a deployment using one vendor does not pay
    for the other's package at cold start.

    Raises `LLMCredentialsError` when that provider has no key - the caller
    decides whether that is fatal or merely means "no fallback available".
    """
    key = provider.strip().lower()

    if key == "anthropic":
        from src.rag.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key,
            # The per-provider variable wins; `llm_model` is only consulted
            # when it actually names a Claude model, so a value left over from
            # the other vendor is ignored rather than sent verbatim.
            model=settings.model_for_provider("anthropic", settings.anthropic_model),
            max_output_tokens=settings.llm_max_output_tokens,
            effort=settings.llm_effort,
        )

    if key == "groq":
        from src.rag.llm.groq_provider import GroqLLMProvider

        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            model=settings.model_for_provider("groq", settings.groq_model),
            max_output_tokens=settings.llm_max_output_tokens,
            effort=settings.llm_effort,
            base_url=settings.groq_base_url,
        )

    raise LLMError(
        f"Unknown AI provider {provider!r}. ResearchForge supports {' and '.join(PROVIDERS)}."
    )


def build_routed_provider(primary: str, settings: Settings) -> RoutedLLMProvider:
    """Build the primary provider with the OTHER one as its fallback.

    Build one PER ANALYSIS: the router remembers whether it has switched, and
    that per-instance state is what limits an analysis to a single change of
    model (see `src/rag/llm/router.py`).

    A fallback that has no API key is simply absent rather than an error. Its
    key belongs to a provider the owner may not have signed up for, and
    refusing to run at all would make the second vendor mandatory - the exact
    opposite of what a fallback is for.
    """
    primary_key = primary.strip().lower()
    if primary_key not in PROVIDERS:
        raise LLMError(
            f"Unknown AI provider {primary!r}. ResearchForge supports {' and '.join(PROVIDERS)}."
        )

    fallback_key = OPPOSITE[primary_key]

    primary_provider = build_provider(primary_key, settings)

    fallback_provider: LLMProvider | None = None
    if settings.has_credentials_for(fallback_key):
        try:
            fallback_provider = build_provider(fallback_key, settings)
        except LLMError:
            # A fallback that cannot be built is no fallback. The analysis
            # still runs on the primary; it just has nowhere to go if that
            # fails, which is strictly better than refusing to start.
            fallback_provider = None

    return RoutedLLMProvider(
        primary=primary_provider,
        primary_key=primary_key,
        fallback=fallback_provider,
        fallback_key=fallback_key if fallback_provider else None,
    )


def get_llm_provider(settings: Settings) -> LLMProvider:
    """The provider named by `settings.llm_provider`, with no routing.

    Retained for callers that want one specific vendor and no fallback. The
    analysis path uses `build_routed_provider` instead.
    """
    return build_provider(settings.llm_provider_name, settings)
