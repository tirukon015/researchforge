"""Provider selection and the Gemini provider's own decisions.

NO NETWORK, NO KEYS, NO TOKENS SPENT. Every test here either exercises pure
logic or drives `GeminiLLMProvider` with a stub standing in for the SDK client,
so the suite runs offline and costs nothing - the same rule `test_analysis.py`
follows with `FakeLLMProvider`.

What is deliberately NOT tested: that Gemini returns good analysis. That is the
vendor's job. What IS tested is everything this project promised on top of it -
that a truncated reply is refused rather than used, that a rejected key stays
distinguishable from a network fault, and that a leftover model name from the
other vendor cannot be sent to Gemini.
"""

import httpx
import pytest
from pydantic import BaseModel

from src.config import Settings
from src.rag.llm import get_llm_provider
from src.rag.llm.base import LLMCredentialsError, LLMError, LLMResponseError
from src.rag.llm.gemini_provider import (
    DEFAULT_MODEL,
    GeminiLLMProvider,
    thinking_level_for_effort,
)


class Tiny(BaseModel):
    """Smallest possible structured output, so tests are about plumbing."""

    answer: str


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #


class _StubInteraction:
    def __init__(self, output_text="", status="completed", errors=None):
        self.output_text = output_text
        self.status = status
        self.errors = errors or []


class _StubError:
    def __init__(self, message):
        self.message = message
        self.code = "TEST"


class _StubInteractions:
    """Records the request and returns a canned reply (or raises)."""

    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raises is not None:
            raise self._raises
        return self._result


class _StubClient:
    def __init__(self, interactions):
        self.interactions = interactions


def _provider(result=None, raises=None, **kwargs) -> GeminiLLMProvider:
    """A provider whose SDK client is a stub. The constructor still runs, so
    credential checking and configuration are exercised for real."""
    p = GeminiLLMProvider(api_key="test-key-not-real", **kwargs)
    p._client = _StubClient(_StubInteractions(result=result, raises=raises))
    return p


def _stub(p: GeminiLLMProvider) -> _StubInteractions:
    return p._client.interactions


# --------------------------------------------------------------------------- #
# Effort mapping
# --------------------------------------------------------------------------- #


class TestThinkingLevel:
    @pytest.mark.parametrize(
        ("effort", "expected"),
        [
            ("minimal", "minimal"),
            ("low", "low"),
            ("medium", "medium"),
            ("high", "high"),
            ("HIGH", "high"),
            ("  low  ", "low"),
        ],
    )
    def test_levels_gemini_supports_pass_through(self, effort, expected) -> None:
        assert thinking_level_for_effort(effort) == expected

    @pytest.mark.parametrize("effort", ["xhigh", "max"])
    def test_levels_above_gemini_map_down_rather_than_failing(self, effort) -> None:
        """Asking for more thought than the vendor offers should get its
        maximum. Rejecting the value would make LLM_EFFORT non-portable."""
        assert thinking_level_for_effort(effort) == "high"

    def test_unknown_effort_falls_back_to_high(self) -> None:
        assert thinking_level_for_effort("banana") == "high"


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #


class TestCredentials:
    @pytest.mark.parametrize("key", ["", "   "])
    def test_missing_key_raises_credentials_error_naming_the_variable(self, key) -> None:
        with pytest.raises(LLMCredentialsError) as exc:
            GeminiLLMProvider(api_key=key)
        assert "GEMINI_API_KEY" in str(exc.value)

    def test_repr_never_exposes_the_key(self) -> None:
        p = _provider()
        text = repr(p)
        assert "test-key-not-real" not in text
        assert "redacted" in text


# --------------------------------------------------------------------------- #
# Request construction
# --------------------------------------------------------------------------- #


class TestRequest:
    def test_structured_request_carries_schema_and_json_mime(self) -> None:
        p = _provider(result=_StubInteraction(output_text='{"answer":"ok"}'))
        p.generate_structured(system="sys", prompt="user", output_model=Tiny)

        sent = _stub(p).last_kwargs
        assert sent["system_instruction"] == "sys"
        assert sent["input"] == "user"
        assert sent["response_format"]["mime_type"] == "application/json"
        # The schema must be the real one, or the model is unconstrained.
        assert sent["response_format"]["schema"]["properties"]["answer"]

    def test_effort_reaches_the_request_as_thinking_level(self) -> None:
        p = _provider(result=_StubInteraction(output_text="hi"), effort="max")
        p.generate_text(system="s", prompt="u")
        assert _stub(p).last_kwargs["generation_config"]["thinking_level"] == "high"

    def test_max_output_tokens_is_forwarded(self) -> None:
        p = _provider(result=_StubInteraction(output_text="hi"), max_output_tokens=1234)
        p.generate_text(system="s", prompt="u")
        assert _stub(p).last_kwargs["generation_config"]["max_output_tokens"] == 1234

    def test_plain_text_request_sends_no_response_format(self) -> None:
        p = _provider(result=_StubInteraction(output_text="hi"))
        p.generate_text(system="s", prompt="u")
        assert "response_format" not in _stub(p).last_kwargs


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #


class TestStructuredOutput:
    def test_valid_json_is_parsed_into_the_model(self) -> None:
        p = _provider(result=_StubInteraction(output_text='{"answer":"42"}'))
        got = p.generate_structured(system="s", prompt="u", output_model=Tiny)
        assert isinstance(got, Tiny)
        assert got.answer == "42"

    def test_output_not_matching_the_schema_is_refused(self) -> None:
        """A schema constrains the model; it does not guarantee the reply.
        A mismatch must fail loudly rather than reach the API layer."""
        p = _provider(result=_StubInteraction(output_text='{"wrong_field":"x"}'))
        with pytest.raises(LLMResponseError) as exc:
            p.generate_structured(system="s", prompt="u", output_model=Tiny)
        assert "schema" in str(exc.value)

    def test_prose_instead_of_json_is_refused(self) -> None:
        p = _provider(result=_StubInteraction(output_text="Sure! Here is the answer."))
        with pytest.raises(LLMResponseError):
            p.generate_structured(system="s", prompt="u", output_model=Tiny)

    def test_empty_output_is_refused(self) -> None:
        p = _provider(result=_StubInteraction(output_text=""))
        with pytest.raises(LLMResponseError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "empty" in str(exc.value)


class TestStatusHandling:
    def test_truncated_response_is_refused_not_used(self) -> None:
        """The dangerous failure: a 200 with valid-looking but partial JSON."""
        p = _provider(
            result=_StubInteraction(output_text='{"answer":"partial"}', status="incomplete")
        )
        with pytest.raises(LLMResponseError) as exc:
            p.generate_structured(system="s", prompt="u", output_model=Tiny)
        assert "cut off" in str(exc.value)

    def test_budget_exceeded_names_it_as_an_operator_problem(self) -> None:
        p = _provider(result=_StubInteraction(output_text="x", status="budget_exceeded"))
        with pytest.raises(LLMResponseError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "operator" in str(exc.value)

    def test_api_error_text_is_appended_rather_than_discarded(self) -> None:
        p = _provider(
            result=_StubInteraction(
                output_text="",
                status="failed",
                errors=[_StubError("safety filter triggered")],
            )
        )
        with pytest.raises(LLMResponseError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "safety filter triggered" in str(exc.value)

    def test_completed_status_is_accepted(self) -> None:
        p = _provider(result=_StubInteraction(output_text="fine", status="completed"))
        assert p.generate_text(system="s", prompt="u") == "fine"


# --------------------------------------------------------------------------- #
# Error translation
# --------------------------------------------------------------------------- #


class _InteractionsError(Exception):
    """Shaped like what `client.interactions` actually raises.

    The real class lives in `google.genai._gaos.lib.compat_errors`, a PRIVATE
    module, and is a DIFFERENT class from the public `google.genai.errors`
    one that `client.models` raises. Production proved the difference matters:
    matching on the public class missed every interactions error, so a rejected
    key would have been reported as a generic 502 instead of a 503.

    Reproducing the shape rather than importing the private class is the point -
    the provider now identifies a failure by the status it carries, so this test
    stays honest without depending on where the SDK keeps its classes.
    """

    def __init__(self, status_code: int, message: str = "boom") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class _PublicApiError(Exception):
    """The other hierarchy: `google.genai.errors.APIError` exposes `code`."""

    def __init__(self, code: int, message: str = "boom") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TestErrorTranslation:
    @pytest.mark.parametrize("error_type", [_InteractionsError, _PublicApiError])
    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_failures_become_credentials_errors(self, error_type, status) -> None:
        """The API layer maps credentials errors to 503 and everything else to
        502, so this distinction has to survive translation - from EITHER of the
        SDK's two error hierarchies."""
        p = _provider(raises=error_type(status))
        with pytest.raises(LLMCredentialsError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "GEMINI_API_KEY" in str(exc.value)

    @pytest.mark.parametrize("error_type", [_InteractionsError, _PublicApiError])
    def test_rate_limit_is_reported_as_retryable(self, error_type) -> None:
        p = _provider(raises=error_type(429, "quota exceeded, retry in 51s"))
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert not isinstance(exc.value, LLMCredentialsError)
        assert "retry" in str(exc.value).lower()
        # The API's own text names the limit and the wait, which is more use to
        # an operator than our generic sentence.
        assert "quota exceeded, retry in 51s" in str(exc.value)

    def test_rate_limit_is_not_reported_as_an_unexpected_failure(self) -> None:
        """Regression guard. This exact case reached production as
        'Unexpected generation failure: Error code: 429', which reads like a
        bug in ResearchForge rather than a quota an operator can act on."""
        p = _provider(raises=_InteractionsError(429, "You exceeded your quota"))
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "Unexpected generation failure" not in str(exc.value)

    @pytest.mark.parametrize("error_type", [_InteractionsError, _PublicApiError])
    def test_server_error_keeps_the_api_message(self, error_type) -> None:
        p = _provider(raises=error_type(500, "internal explosion"))
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "internal explosion" in str(exc.value)

    def test_timeout_is_named_as_a_timeout(self) -> None:
        p = _provider(raises=httpx.ReadTimeout("too slow"))
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "timed out" in str(exc.value)

    def test_timeout_wrapped_by_the_sdk_is_still_named_a_timeout(self) -> None:
        """The SDK re-raises httpx failures as its own connection classes with
        `raise ... from exc`, so the useful identity is on the cause."""
        wrapped = RuntimeError("Request timed out.")
        wrapped.__cause__ = httpx.ReadTimeout("too slow")
        p = _provider(raises=wrapped)
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "timed out" in str(exc.value)

    def test_connection_failure_is_named_as_connectivity(self) -> None:
        p = _provider(raises=httpx.ConnectError("no route"))
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "reach the Gemini API" in str(exc.value)

    def test_a_connection_class_with_no_status_is_not_read_as_an_api_error(self) -> None:
        """A connection failure never got a response, so it has no status code.
        Treating it as one would report a network fault as an API error."""
        wrapped = RuntimeError("Connection error.")
        wrapped.__cause__ = httpx.ConnectError("no route")
        p = _provider(raises=wrapped)
        with pytest.raises(LLMError) as exc:
            p.generate_text(system="s", prompt="u")
        assert "reach the Gemini API" in str(exc.value)

    def test_unexpected_exception_still_becomes_an_llm_error(self) -> None:
        """Nothing may escape as a raw vendor/runtime exception - the API layer
        would turn it into a 500 stack trace."""
        p = _provider(raises=RuntimeError("something odd"))
        with pytest.raises(LLMError):
            p.generate_text(system="s", prompt="u")


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


class TestProviderSelection:
    def test_gemini_is_selected_and_built(self) -> None:
        p = get_llm_provider(Settings(_env_file=None, llm_provider="gemini", gemini_api_key="k"))
        assert isinstance(p, GeminiLLMProvider)
        assert p.model_name == DEFAULT_MODEL

    def test_selection_is_case_and_whitespace_insensitive(self) -> None:
        p = get_llm_provider(Settings(_env_file=None, llm_provider="  Gemini ", gemini_api_key="k"))
        assert isinstance(p, GeminiLLMProvider)

    def test_missing_gemini_key_raises_credentials_error(self) -> None:
        with pytest.raises(LLMCredentialsError) as exc:
            get_llm_provider(Settings(_env_file=None, llm_provider="gemini", gemini_api_key=""))
        assert "GEMINI_API_KEY" in str(exc.value)

    def test_anthropic_key_does_not_satisfy_gemini(self) -> None:
        """Two vendors wired up means a leftover key for the wrong one must not
        make the app look ready - the failure would surface mid-analysis."""
        settings = Settings(
            _env_file=None,
            llm_provider="gemini",
            anthropic_api_key="left-over",
            gemini_api_key="",
        )
        assert settings.has_llm_credentials is False
        with pytest.raises(LLMCredentialsError):
            get_llm_provider(settings)

    def test_unknown_provider_lists_the_supported_ones(self) -> None:
        with pytest.raises(LLMError) as exc:
            get_llm_provider(Settings(_env_file=None, llm_provider="hal9000"))
        message = str(exc.value)
        assert "anthropic" in message and "gemini" in message

    def test_model_name_from_the_other_vendor_is_ignored(self) -> None:
        """Switching LLM_PROVIDER alone must produce a working configuration,
        not a request for 'claude-opus-5' sent to Gemini."""
        p = get_llm_provider(
            Settings(
                _env_file=None,
                llm_provider="gemini",
                llm_model="claude-opus-5",
                gemini_api_key="k",
            )
        )
        assert p.model_name == DEFAULT_MODEL

    def test_an_explicit_gemini_model_is_honoured(self) -> None:
        p = get_llm_provider(
            Settings(
                _env_file=None,
                llm_provider="gemini",
                llm_model="gemini-2.5-pro",
                gemini_api_key="k",
            )
        )
        assert p.model_name == "gemini-2.5-pro"
