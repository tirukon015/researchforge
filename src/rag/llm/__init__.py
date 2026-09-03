"""LLM providers.

Import `LLMProvider` and the error types from here. Never import a concrete
provider outside `get_llm_provider` - that would couple the pipeline to one
vendor and defeat the abstraction (same rule as `src/rag/embeddings`).
"""

from src.config import Settings
from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
)

__all__ = [
    "LLMCredentialsError",
    "LLMError",
    "LLMProvider",
    "LLMRateLimitError",
    "LLMResponseError",
    "get_llm_provider",
]


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Build the provider named by `settings.llm_provider`.

    The import is local so adding a provider never forces every caller to
    import every vendor SDK.
    """
    provider = settings.llm_provider.strip().lower()

    if provider == "anthropic":
        from src.rag.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            max_output_tokens=settings.llm_max_output_tokens,
            effort=settings.llm_effort,
        )

    if provider == "gemini":
        from src.rag.llm.gemini_provider import DEFAULT_MODEL, GeminiLLMProvider

        return GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            # LLM_MODEL is shared across providers, so a value left over from
            # another vendor would be sent to Gemini verbatim and rejected as
            # an unknown model. Falling back to this provider's own default
            # makes LLM_PROVIDER switchable on its own, which is the whole
            # point of the abstraction.
            model=settings.model_for_provider(provider, DEFAULT_MODEL),
            max_output_tokens=settings.llm_max_output_tokens,
            effort=settings.llm_effort,
        )

    raise LLMError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Supported values: 'anthropic', 'gemini'."
    )
