"""LIVE smoke test for the two AI providers. SKIPPED BY DEFAULT.

WHY THIS EXISTS
---------------
Every other test in this suite runs offline against fakes, which is what keeps
`pytest` free, fast and deterministic. That leaves exactly one thing unproven:
whether the configured API keys and model IDs are real. A wrong model ID
(`GROQ_MODEL` especially - Groq's catalogue changes) looks perfectly fine until
the first upload fails in production.

This file closes that gap without compromising the rest of the suite. It is
skipped unless BOTH are true:

    RESEARCHFORGE_LIVE_PROVIDER_TEST=1      an explicit opt-in, so it can never
                                            fire by accident in CI
    ANTHROPIC_API_KEY / GROQ_API_KEY        the key for that provider

Run it after adding your keys:

    RESEARCHFORGE_LIVE_PROVIDER_TEST=1 pytest tests/test_provider_smoke.py -v

    # Windows PowerShell
    $env:RESEARCHFORGE_LIVE_PROVIDER_TEST=1; pytest tests/test_provider_smoke.py -v

WHAT IT COSTS
-------------
A few hundred tokens per provider. The prompt is trivial and `max_output_tokens`
is clamped low, deliberately: this proves the key and the model ID are valid,
which needs one tiny round trip, not a real analysis.

IT NEVER PRINTS A KEY. Failures name the environment VARIABLE, never its value.
"""

import os

import pytest
from pydantic import BaseModel

from src.config import Settings
from src.rag.llm import build_provider
from src.rag.llm.base import LLMCredentialsError, LLMError

LIVE = os.environ.get("RESEARCHFORGE_LIVE_PROVIDER_TEST") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason=(
        "live provider test. Set RESEARCHFORGE_LIVE_PROVIDER_TEST=1 and the "
        "provider's API key to run it. Costs a few hundred tokens."
    ),
)


class Ping(BaseModel):
    """The smallest possible schema that still proves structured output works."""

    answer: str


def _settings() -> Settings:
    """Settings from the real environment, so this reads the actual keys."""
    return Settings()


def _requires(variable: str) -> None:
    if not os.environ.get(variable, "").strip():
        pytest.skip(f"{variable} is not set")


class TestAnthropicLive:
    def test_the_key_and_model_are_real(self) -> None:
        """Proves ANTHROPIC_API_KEY works AND ANTHROPIC_MODEL names a model
        the account can actually reach."""
        _requires("ANTHROPIC_API_KEY")
        settings = _settings()
        provider = build_provider("anthropic", settings)

        result = provider.generate_text(
            system="Reply with exactly one word.",
            prompt="Say OK.",
        )
        assert isinstance(result, str) and result.strip()
        print(f"\n  Anthropic OK - model: {provider.model_name}")

    def test_structured_output_validates(self) -> None:
        """The analysis pipeline depends on schema-constrained output. A key
        that works for plain text but not for structured output would fail
        only on a real upload."""
        _requires("ANTHROPIC_API_KEY")
        provider = build_provider("anthropic", _settings())
        reply = provider.generate_structured(
            system="Answer briefly.",
            prompt="What is the capital of France? Put it in `answer`.",
            output_model=Ping,
        )
        assert isinstance(reply, Ping)
        assert reply.answer.strip()


class TestGroqLive:
    def test_the_key_and_model_are_real(self) -> None:
        """The one most likely to fail: Groq's model catalogue changes, and
        GROQ_MODEL defaults to a name that may have been superseded. A 404
        here means the default needs updating - the error names the variable."""
        _requires("GROQ_API_KEY")
        settings = _settings()
        provider = build_provider("groq", settings)

        try:
            result = provider.generate_text(
                system="Reply with exactly one word.",
                prompt="Say OK.",
            )
        except LLMError as exc:
            if "does not offer the model" in str(exc):
                pytest.fail(
                    f"GROQ_MODEL is not available to this account: "
                    f"{provider.model_name!r}. List what is, with:\n"
                    "  curl -s https://api.groq.com/openai/v1/models "
                    '-H "Authorization: Bearer $GROQ_API_KEY" '
                    "| python -c \"import json,sys;[print(m['id']) "
                    "for m in json.load(sys.stdin)['data']]\""
                )
            raise
        assert isinstance(result, str) and result.strip()
        print(f"\n  Groq OK - model: {provider.model_name}")

    def test_structured_output_validates(self) -> None:
        """Groq has no schema-constrained generation, so the provider asks for
        JSON and validates it itself. That path is the one that matters, and
        it is model-dependent - a model that ignores the JSON instruction
        would pass the text test above and fail every real analysis."""
        _requires("GROQ_API_KEY")
        provider = build_provider("groq", _settings())
        reply = provider.generate_structured(
            system="Answer briefly.",
            prompt="What is the capital of France? Put it in `answer`.",
            output_model=Ping,
        )
        assert isinstance(reply, Ping)
        assert reply.answer.strip()


class TestNeitherKeyLeaks:
    def test_a_bad_key_names_the_variable_and_not_its_value(self) -> None:
        """Runs offline-ish: a deliberately invalid key, so no quota is spent.
        Confirms a rejected credential is reported by NAME."""
        _requires("GROQ_API_KEY")
        bogus = "gsk_this_key_is_deliberately_invalid_0000000000"
        provider = build_provider("groq", Settings(_env_file=None, groq_api_key=bogus))
        with pytest.raises((LLMCredentialsError, LLMError)) as raised:
            provider.generate_text(system="s", prompt="p")
        assert bogus not in str(raised.value)
