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
    LLMResponseError,
)

__all__ = [
    "LLMCredentialsError",
    "LLMError",
    "LLMProvider",
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

    raise LLMError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}. "
        "Supported values: 'anthropic'. Decision D5 is still open - see "
        "CLAUDE.md section 9."
    )
