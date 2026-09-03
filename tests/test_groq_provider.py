"""`GroqLLMProvider` driven against a mock of Groq's HTTP API.

WHY THIS FILE EXISTS
--------------------
Groq has no schema-constrained generation of the kind Anthropic's
`messages.parse` provides, so this provider gets its structured output by
asking for JSON, supplying the schema, and validating the reply itself. That
validation step is the whole reason the provider can be trusted, and it is
exactly the kind of code that looks right and is not - so every branch of it is
exercised here.

The most important test in the file is
`test_output_that_fails_validation_is_discarded_not_repaired`. Silently
patching up a near-miss would turn a grounded analysis into an invented one,
which is the single thing this project must never do.

NO NETWORK, NO API KEY. httpx's MockTransport intercepts every request, and
the replies are shaped as Groq's OpenAI-compatible API documents them.
"""

import json

import httpx
import pytest
from pydantic import BaseModel

from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
)
from src.rag.llm.groq_provider import DEFAULT_MODEL, GroqLLMProvider

FAKE_KEY = "not-a-real-groq-key-for-tests-only"


class Analysis(BaseModel):
    problem: str
    findings: list[str]


@pytest.fixture
def transport(monkeypatch):
    """Route every httpx.Client the provider builds through a mock."""
    holder: dict[str, httpx.MockTransport] = {}
    original = httpx.Client

    def patched(*args, **kwargs):
        if "transport" not in kwargs and "mock" in holder:
            kwargs["transport"] = holder["mock"]
        return original(*args, **kwargs)

    monkeypatch.setattr("src.rag.llm.groq_provider.httpx.Client", patched)

    def install(handler):
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        holder["mock"] = httpx.MockTransport(recording)
        return seen

    return install


def completion(content: str, *, finish_reason: str = "stop") -> httpx.Response:
    """A reply shaped the way Groq's chat-completions endpoint sends one."""
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish_reason,
                    "message": {"role": "assistant", "content": content},
                }
            ],
        },
    )


def provider(**kwargs) -> GroqLLMProvider:
    return GroqLLMProvider(api_key=FAKE_KEY, **kwargs)


VALID = json.dumps({"problem": "Whether attention suffices.", "findings": ["Higher BLEU."]})


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


class TestConstruction:
    def test_a_missing_key_is_refused_and_names_the_variable(self) -> None:
        with pytest.raises(LLMCredentialsError) as raised:
            GroqLLMProvider(api_key="")
        assert "GROQ_API_KEY" in str(raised.value)

    def test_whitespace_is_not_a_key(self) -> None:
        with pytest.raises(LLMCredentialsError):
            GroqLLMProvider(api_key="   ")

    def test_the_default_model_is_the_documented_one(self) -> None:
        assert provider().model_name == DEFAULT_MODEL
        assert DEFAULT_MODEL == "qwen/qwen3.6-27b"

    def test_the_model_is_configurable(self) -> None:
        assert provider(model="qwen/qwen3.6-32b").model_name == "qwen/qwen3.6-32b"

    def test_a_trailing_slash_on_the_base_url_does_not_double_up(self, transport) -> None:
        seen = transport(lambda r: completion(VALID))
        provider(base_url="https://api.groq.com/openai/v1/").generate_text(system="s", prompt="p")
        assert str(seen[0].url).endswith("/openai/v1/chat/completions")


# --------------------------------------------------------------------------- #
# The request that goes out
# --------------------------------------------------------------------------- #


class TestRequestShape:
    def test_the_key_is_sent_as_a_bearer_token(self, transport) -> None:
        seen = transport(lambda r: completion(VALID))
        provider().generate_text(system="s", prompt="p")
        assert seen[0].headers["authorization"] == f"Bearer {FAKE_KEY}"

    def test_a_structured_call_asks_for_json(self, transport) -> None:
        seen = transport(lambda r: completion(VALID))
        provider().generate_structured(system="s", prompt="p", output_model=Analysis)
        body = json.loads(seen[0].content)
        assert body["response_format"] == {"type": "json_object"}

    def test_the_schema_is_supplied_verbatim(self, transport) -> None:
        """Supplied, not described. A prose description is a second source of
        truth that drifts away from the Pydantic model."""
        seen = transport(lambda r: completion(VALID))
        provider().generate_structured(system="s", prompt="p", output_model=Analysis)
        system = json.loads(seen[0].content)["messages"][0]["content"]
        assert "findings" in system and "problem" in system

    def test_a_plain_text_call_does_not_ask_for_json(self, transport) -> None:
        seen = transport(lambda r: completion("a digest"))
        provider().generate_text(system="s", prompt="p")
        assert "response_format" not in json.loads(seen[0].content)

    def test_high_effort_lowers_the_temperature(self) -> None:
        """Groq has no thinking-budget parameter, so 'effort' maps onto
        determinism. Analytical work wants the lower temperature."""
        assert provider(effort="high")._temperature < provider(effort="low")._temperature


# --------------------------------------------------------------------------- #
# Reading the reply
# --------------------------------------------------------------------------- #


class TestStructuredOutput:
    def test_valid_json_becomes_a_validated_model(self, transport) -> None:
        transport(lambda r: completion(VALID))
        result = provider().generate_structured(system="s", prompt="p", output_model=Analysis)
        assert isinstance(result, Analysis)
        assert result.problem == "Whether attention suffices."
        assert result.findings == ["Higher BLEU."]

    def test_a_markdown_fence_is_tolerated(self, transport) -> None:
        """A fence is the commonest way an otherwise perfect reply becomes
        unparseable. The JSON inside is untouched - if it is wrong, the call
        still fails."""
        transport(lambda r: completion(f"```json\n{VALID}\n```"))
        result = provider().generate_structured(system="s", prompt="p", output_model=Analysis)
        assert result.problem == "Whether attention suffices."

    def test_output_that_fails_validation_is_discarded_not_repaired(self, transport) -> None:
        """THE test in this file.

        `findings` is a string where a list is required. A provider that
        coerced or patched this would be inventing part of an analysis the
        model did not produce, and every grounding claim the project makes
        would be void. It must fail instead.
        """
        transport(lambda r: completion(json.dumps({"problem": "p", "findings": "not a list"})))
        with pytest.raises(LLMResponseError) as raised:
            provider().generate_structured(system="s", prompt="p", output_model=Analysis)
        assert "discarded" in str(raised.value).lower()

    def test_a_missing_field_is_not_filled_in(self, transport) -> None:
        transport(lambda r: completion(json.dumps({"problem": "p"})))
        with pytest.raises(LLMResponseError):
            provider().generate_structured(system="s", prompt="p", output_model=Analysis)

    def test_prose_instead_of_json_is_an_error(self, transport) -> None:
        transport(lambda r: completion("Certainly! Here is the analysis you asked for."))
        with pytest.raises(LLMResponseError):
            provider().generate_structured(system="s", prompt="p", output_model=Analysis)

    def test_a_truncated_reply_is_refused(self, transport) -> None:
        """A response cut off at the token ceiling is incomplete, not merely
        short. Returning it would silently drop the end of an analysis."""
        transport(lambda r: completion(VALID, finish_reason="length"))
        with pytest.raises(LLMResponseError) as raised:
            provider().generate_structured(system="s", prompt="p", output_model=Analysis)
        assert "cut off" in str(raised.value).lower()

    def test_an_empty_completion_is_an_error(self, transport) -> None:
        transport(lambda r: completion("   "))
        with pytest.raises(LLMResponseError):
            provider().generate_text(system="s", prompt="p")

    def test_no_choices_is_an_error(self, transport) -> None:
        transport(lambda r: httpx.Response(200, json={"choices": []}))
        with pytest.raises(LLMResponseError):
            provider().generate_text(system="s", prompt="p")


# --------------------------------------------------------------------------- #
# Failure translation
# --------------------------------------------------------------------------- #


class TestFailures:
    def test_a_429_becomes_a_rate_limit_error(self, transport) -> None:
        transport(lambda r: httpx.Response(429, json={"error": {"message": "rate limit reached"}}))
        with pytest.raises(LLMRateLimitError):
            provider().generate_text(system="s", prompt="p")

    def test_retry_after_is_read_when_the_provider_states_it(self, transport) -> None:
        transport(
            lambda r: httpx.Response(
                429, headers={"retry-after": "30"}, json={"error": {"message": "slow down"}}
            )
        )
        with pytest.raises(LLMRateLimitError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert raised.value.retry_after_seconds == 30

    def test_groqs_own_reset_header_is_understood(self, transport) -> None:
        """Groq reports remaining allowance as e.g. "2m59.5s" rather than as
        Retry-After. Ignoring it would discard timing the provider gave us."""
        transport(
            lambda r: httpx.Response(
                429,
                headers={"x-ratelimit-reset-requests": "2m30s"},
                json={"error": {"message": "rate limit"}},
            )
        )
        with pytest.raises(LLMRateLimitError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert raised.value.retry_after_seconds == 150

    def test_an_absent_delay_stays_absent(self, transport) -> None:
        """None means "not known", never zero. A guess would be counted down
        in the interface as though the provider had said it."""
        transport(lambda r: httpx.Response(429, json={"error": {"message": "rate limit"}}))
        with pytest.raises(LLMRateLimitError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert raised.value.retry_after_seconds is None

    def test_a_daily_quota_is_flagged_as_exhausted(self, transport) -> None:
        """Telling someone to retry in a minute when their daily allowance is
        gone wastes the little that remains."""
        transport(
            lambda r: httpx.Response(
                429, json={"error": {"message": "You have exceeded your requests per day."}}
            )
        )
        with pytest.raises(LLMRateLimitError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert raised.value.quota_exhausted is True

    def test_a_short_delay_is_not_flagged_as_exhausted(self, transport) -> None:
        transport(
            lambda r: httpx.Response(
                429, headers={"retry-after": "5"}, json={"error": {"message": "slow down"}}
            )
        )
        with pytest.raises(LLMRateLimitError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert raised.value.quota_exhausted is False

    @pytest.mark.parametrize("status", [401, 403])
    def test_a_rejected_key_is_a_credentials_error(self, transport, status) -> None:
        """NOT retryable: the other provider's key is a different variable, and
        masking this would leave a deployment fault unreported."""
        transport(lambda r: httpx.Response(status, json={"error": {"message": "invalid"}}))
        with pytest.raises(LLMCredentialsError):
            provider().generate_text(system="s", prompt="p")

    def test_an_unknown_model_names_the_variable_to_fix(self, transport) -> None:
        transport(
            lambda r: httpx.Response(
                404, json={"error": {"message": "model not found", "code": "model_not_found"}}
            )
        )
        with pytest.raises(LLMError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert "GROQ_MODEL" in str(raised.value)

    def test_a_server_error_is_a_plain_llm_error_so_it_can_fall_back(self, transport) -> None:
        """Bare LLMError is what `is_retryable` treats as transient, which is
        how a Groq outage reaches Claude."""
        transport(lambda r: httpx.Response(503, text="unavailable"))
        with pytest.raises(LLMError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert not isinstance(raised.value, (LLMCredentialsError, LLMResponseError))

    def test_a_timeout_is_retryable(self, transport) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        transport(handler)
        with pytest.raises(LLMError) as raised:
            provider().generate_text(system="s", prompt="p")
        assert not isinstance(raised.value, (LLMCredentialsError, LLMResponseError))

    def test_no_error_message_ever_contains_the_key(self, transport) -> None:
        for status in (401, 429, 500):
            transport(lambda r, s=status: httpx.Response(s, json={"error": {"message": "x"}}))
            with pytest.raises(LLMError) as raised:
                provider().generate_text(system="s", prompt="p")
            assert FAKE_KEY not in str(raised.value)
