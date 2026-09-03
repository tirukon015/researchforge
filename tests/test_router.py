"""Primary provider selection and automatic fallback.

WHAT THIS FILE IS FOR
---------------------
ResearchForge runs on two providers. The owner picks one as primary; the other
is automatically the fallback. The rules that make that safe rather than merely
clever are:

  * fall back ONLY for retryable failures,
  * fall back AT MOST ONCE per analysis, and stay switched afterwards,
  * record the provider that ACTUALLY produced the result, not the one that
    was configured.

Each of those is a way the feature could quietly do the wrong thing, so each
has tests. The third matters most for academic honesty: a stored analysis that
credits Claude when Groq wrote it is a fabricated provenance record.

NO NETWORK, NO API KEYS. Both providers are fakes that fail on command.
"""

import pytest
from pydantic import BaseModel

from src.config import Settings
from src.rag.llm import build_routed_provider
from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
)
from src.rag.llm.router import (
    OPPOSITE,
    PROVIDERS,
    RoutedLLMProvider,
    display_name,
    is_retryable,
)


class Reply(BaseModel):
    text: str


class FakeProvider(LLMProvider):
    """A provider that answers, or fails with whatever it was given."""

    def __init__(self, name: str, *, fail_with: Exception | None = None, fail_times: int = 0):
        self._name = name
        self.fail_with = fail_with
        # `fail_times = 0` with a fail_with means "fail every time".
        self.fail_times = fail_times
        self.calls = 0

    @property
    def model_name(self) -> str:
        return self._name

    def _maybe_fail(self):
        self.calls += 1
        if self.fail_with is None:
            return
        if self.fail_times == 0 or self.calls <= self.fail_times:
            raise self.fail_with

    def generate_structured(self, *, system, prompt, output_model):
        self._maybe_fail()
        return output_model(text=f"{self._name} structured")

    def generate_text(self, *, system, prompt) -> str:
        self._maybe_fail()
        return f"{self._name} text"


def routed(primary: FakeProvider, fallback: FakeProvider | None, *, primary_key="anthropic"):
    return RoutedLLMProvider(
        primary=primary,
        primary_key=primary_key,
        fallback=fallback,
        fallback_key=OPPOSITE[primary_key] if fallback else None,
    )


def call(provider: RoutedLLMProvider) -> Reply:
    return provider.generate_structured(system="s", prompt="p", output_model=Reply)


# --------------------------------------------------------------------------- #
# The shape of the configuration
# --------------------------------------------------------------------------- #


class TestProviderPairing:
    def test_there_are_exactly_two_providers(self) -> None:
        """The architecture is a PAIR. A third would make "the fallback"
        ambiguous, which is why there is no "auto" option to choose."""
        assert set(PROVIDERS) == {"anthropic", "groq"}

    def test_each_provider_falls_back_to_the_other(self) -> None:
        assert OPPOSITE["anthropic"] == "groq"
        assert OPPOSITE["groq"] == "anthropic"

    def test_the_pairing_is_symmetric(self) -> None:
        """A one-way mapping would let a provider be its own fallback, which
        would retry the thing that just failed."""
        for provider in PROVIDERS:
            assert OPPOSITE[OPPOSITE[provider]] == provider
            assert OPPOSITE[provider] != provider

    def test_providers_have_human_labels(self) -> None:
        assert display_name("anthropic") == "Claude"
        assert display_name("groq") == "Groq Qwen 3.6 27B"

    def test_an_unknown_key_falls_back_to_itself_rather_than_crashing(self) -> None:
        """A label is cosmetic. It must never be the reason a page 500s."""
        assert display_name("something-new") == "something-new"


# --------------------------------------------------------------------------- #
# Which failures justify a second provider
# --------------------------------------------------------------------------- #


class TestRetryability:
    @pytest.mark.parametrize(
        "exc",
        [
            LLMRateLimitError("429"),
            LLMRateLimitError("429", retry_after_seconds=30),
            LLMError("upstream 503"),
            LLMError("connection reset"),
        ],
    )
    def test_transient_failures_are_retryable(self, exc) -> None:
        assert is_retryable(exc) is True

    @pytest.mark.parametrize(
        "exc",
        [
            LLMCredentialsError("ANTHROPIC_API_KEY is not set"),
            LLMResponseError("output did not match the schema"),
        ],
    )
    def test_permanent_failures_are_not_retryable(self, exc) -> None:
        """Retrying these on the other vendor spends a second quota to produce
        the same error, and hides the real cause behind whichever message the
        fallback happened to give."""
        assert is_retryable(exc) is False

    @pytest.mark.parametrize("exc", [ValueError("bug"), KeyError("bug"), RuntimeError("bug")])
    def test_unrecognised_errors_are_not_retryable(self, exc) -> None:
        """A whitelist, not a blacklist. A failure mode nobody has thought
        about yet must not quietly start costing two quotas per analysis."""
        assert is_retryable(exc) is False


# --------------------------------------------------------------------------- #
# Fallback behaviour
# --------------------------------------------------------------------------- #


class TestFallback:
    def test_a_healthy_primary_is_never_left(self) -> None:
        primary = FakeProvider("claude")
        fallback = FakeProvider("qwen")
        provider = routed(primary, fallback)

        assert call(provider).text == "claude structured"
        assert fallback.calls == 0
        assert provider.fallback_used is False

    def test_a_rate_limited_primary_falls_back(self) -> None:
        primary = FakeProvider("claude", fail_with=LLMRateLimitError("429"))
        fallback = FakeProvider("qwen")
        provider = routed(primary, fallback)

        assert call(provider).text == "qwen structured"
        assert provider.fallback_used is True
        assert provider.active_key == "groq"

    def test_a_temporary_failure_falls_back(self) -> None:
        primary = FakeProvider("claude", fail_with=LLMError("upstream 503"))
        provider = routed(primary, FakeProvider("qwen"))
        assert call(provider).text == "qwen structured"
        assert provider.fallback_used is True

    def test_a_credentials_error_does_NOT_fall_back(self) -> None:
        """A missing key is a deployment fault. Masking it with the other
        vendor would leave it broken and unreported."""
        primary = FakeProvider("claude", fail_with=LLMCredentialsError("no key"))
        fallback = FakeProvider("qwen")
        provider = routed(primary, fallback)

        with pytest.raises(LLMCredentialsError):
            call(provider)
        assert fallback.calls == 0
        assert provider.fallback_used is False

    def test_an_unusable_response_does_NOT_fall_back(self) -> None:
        primary = FakeProvider("claude", fail_with=LLMResponseError("bad schema"))
        fallback = FakeProvider("qwen")
        provider = routed(primary, fallback)

        with pytest.raises(LLMResponseError):
            call(provider)
        assert fallback.calls == 0

    def test_with_no_fallback_the_primary_error_is_raised_unchanged(self) -> None:
        """A deployment with one key must report that provider's own error,
        not a wrapped one about a fallback that does not exist."""
        primary = FakeProvider("claude", fail_with=LLMRateLimitError("429"))
        provider = routed(primary, None)

        with pytest.raises(LLMRateLimitError):
            call(provider)

    def test_when_both_fail_the_error_names_both(self) -> None:
        """Reporting only the second failure would send someone to debug the
        wrong vendor."""
        primary = FakeProvider("claude", fail_with=LLMRateLimitError("primary is rate limited"))
        fallback = FakeProvider("qwen", fail_with=LLMError("fallback is down"))
        provider = routed(primary, fallback)

        with pytest.raises(LLMError) as raised:
            call(provider)
        message = str(raised.value)
        assert "Claude" in message and "Groq" in message
        assert "primary is rate limited" in message
        assert "fallback is down" in message

    def test_there_is_no_third_attempt(self) -> None:
        primary = FakeProvider("claude", fail_with=LLMRateLimitError("429"))
        fallback = FakeProvider("qwen", fail_with=LLMError("down"))
        provider = routed(primary, fallback)

        with pytest.raises(LLMError):
            call(provider)
        assert primary.calls == 1
        assert fallback.calls == 1


class TestOneSwitchPerAnalysis:
    """An analysis makes several calls. It must not bounce between vendors."""

    def test_after_switching_every_later_call_uses_the_fallback(self) -> None:
        """The primary recovers after one failure, and is still not returned
        to. Half an analysis by each model would make the recorded 'model
        used' a fiction."""
        primary = FakeProvider("claude", fail_with=LLMRateLimitError("429"), fail_times=1)
        fallback = FakeProvider("qwen")
        provider = routed(primary, fallback)

        assert call(provider).text == "qwen structured"
        assert call(provider).text == "qwen structured"
        assert provider.generate_text(system="s", prompt="p") == "qwen text"

        # One attempt on the primary, ever.
        assert primary.calls == 1
        assert fallback.calls == 3

    def test_the_primary_is_not_retried_even_if_it_would_now_succeed(self) -> None:
        primary = FakeProvider("claude", fail_with=LLMError("blip"), fail_times=1)
        provider = routed(primary, FakeProvider("qwen"))
        call(provider)
        call(provider)
        assert primary.calls == 1

    def test_a_fresh_router_starts_on_the_primary_again(self) -> None:
        """The switch is per-analysis, not permanent. One rate limit must not
        move the whole deployment onto the other vendor for good."""
        primary = FakeProvider("claude", fail_with=LLMRateLimitError("429"), fail_times=1)
        first = routed(primary, FakeProvider("qwen"))
        call(first)
        assert first.fallback_used is True

        second = routed(FakeProvider("claude"), FakeProvider("qwen"))
        assert call(second).text == "claude structured"
        assert second.fallback_used is False


# --------------------------------------------------------------------------- #
# What gets recorded
# --------------------------------------------------------------------------- #


class TestRecordedProvenance:
    def test_the_model_name_is_the_one_that_actually_ran(self) -> None:
        """THE test for honest provenance. Claude was configured, Groq wrote
        the result, and the stored record must say Groq."""
        primary = FakeProvider("claude-opus-5", fail_with=LLMRateLimitError("429"))
        fallback = FakeProvider("qwen/qwen3.6-27b")
        provider = routed(primary, fallback)

        call(provider)
        assert provider.model_name == "qwen/qwen3.6-27b"
        assert provider.active_key == "groq"
        assert provider.fallback_used is True

    def test_without_a_fallback_the_primary_is_reported(self) -> None:
        provider = routed(FakeProvider("claude-opus-5"), FakeProvider("qwen/qwen3.6-27b"))
        call(provider)
        assert provider.model_name == "claude-opus-5"
        assert provider.active_key == "anthropic"

    def test_the_reason_for_the_switch_is_recorded(self) -> None:
        provider = routed(
            FakeProvider("claude", fail_with=LLMRateLimitError("429")), FakeProvider("qwen")
        )
        call(provider)
        assert provider.fallback_reason == "LLMRateLimitError"

    def test_no_switch_means_no_reason(self) -> None:
        provider = routed(FakeProvider("claude"), FakeProvider("qwen"))
        call(provider)
        assert provider.fallback_reason is None

    def test_elapsed_time_is_measured_not_estimated(self) -> None:
        provider = routed(FakeProvider("claude"), FakeProvider("qwen"))
        call(provider)
        # A real measurement from a monotonic clock: non-negative, and small
        # for work this trivial. Asserting a range rather than a value is the
        # only honest thing to assert about a duration.
        assert 0 <= provider.elapsed_ms < 10_000


# --------------------------------------------------------------------------- #
# Building the pair from settings
# --------------------------------------------------------------------------- #


class TestBuildRoutedProvider:
    def test_the_other_provider_becomes_the_fallback(self) -> None:
        provider = build_routed_provider(
            "anthropic",
            Settings(_env_file=None, anthropic_api_key="a", groq_api_key="g"),
        )
        assert provider.active_key == "anthropic"
        assert provider._fallback_key == "groq"

    def test_choosing_groq_makes_claude_the_fallback(self) -> None:
        provider = build_routed_provider(
            "groq",
            Settings(_env_file=None, anthropic_api_key="a", groq_api_key="g"),
        )
        assert provider.active_key == "groq"
        assert provider._fallback_key == "anthropic"

    def test_a_fallback_with_no_key_is_simply_absent(self) -> None:
        """Its key belongs to a vendor the owner may not have signed up for.
        Refusing to run would make the second provider mandatory, which is the
        opposite of what a fallback is for."""
        provider = build_routed_provider(
            "anthropic", Settings(_env_file=None, anthropic_api_key="a", groq_api_key="")
        )
        assert provider.active_key == "anthropic"
        assert provider._fallback_key is None

    def test_a_missing_primary_key_is_still_an_error(self) -> None:
        with pytest.raises(LLMCredentialsError):
            build_routed_provider(
                "anthropic", Settings(_env_file=None, anthropic_api_key="", groq_api_key="g")
            )

    def test_gemini_cannot_be_chosen_as_primary(self) -> None:
        """Retired from the active workflow. A stale configuration value must
        fail loudly rather than resurrect a third provider."""
        with pytest.raises(LLMError) as raised:
            build_routed_provider(
                "gemini", Settings(_env_file=None, gemini_api_key="g", anthropic_api_key="a")
            )
        assert "anthropic" in str(raised.value) and "groq" in str(raised.value)

    def test_an_unknown_provider_is_refused(self) -> None:
        with pytest.raises(LLMError):
            build_routed_provider("hal9000", Settings(_env_file=None))
