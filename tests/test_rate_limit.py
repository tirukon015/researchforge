"""Gemini rate limiting: detection, classification, and deliberate restraint.

NO NETWORK, NO KEYS, NO TOKENS SPENT, AND NO REAL SLEEPING. Every test drives
`GeminiLLMProvider` with a stub in place of the SDK client, and the one test
that exercises the wait replaces `time.sleep` so the suite stays fast.

WHAT THESE TESTS ARE REALLY DEFENDING
-------------------------------------
The bug being guarded against is not "a 429 is unhandled". It is the opposite:
the SDK retries 429 four times per call by default, a paper is three calls, and
a free tier of twenty requests is therefore spent by ONE rate-limited analysis
retrying itself. Most of what follows asserts that a request is NOT made:

  - the SDK is configured so 429 is not in its retryable set at all
  - an exhausted quota is never retried
  - a rate limit with no stated delay is never retried
  - a delay beyond the cap is never retried
  - a retry happens at most once, never in a loop
  - the waiting budget is shared across an analysis, not per call

The remaining tests assert the two claims the interface makes on top: that a
429 stays a 429 rather than becoming a 502, and that "wait forty seconds" is
told apart from "your daily allowance is gone".
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api.analyze import get_provider
from src.config import Settings, get_settings
from src.main import app
from src.rag.llm.base import LLMError, LLMRateLimitError
from src.rag.llm.gemini_provider import (
    MAX_RETRY_WAIT_SECONDS,
    RATE_LIMIT_WAIT_BUDGET_SECONDS,
    GeminiLLMProvider,
    _looks_exhausted,
    _retry_delay_from_body,
)
from tests.pdf_fixtures import build_text_pdf
from tests.test_analysis import PAPER_TEXT, FakeLLMProvider


class Tiny(BaseModel):
    answer: str


# --------------------------------------------------------------------------- #
# Stubs shaped like the SDK's real 429
# --------------------------------------------------------------------------- #


def quota_body(
    *,
    retry_delay: str | None = "44s",
    quota_id: str = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
    metric: str = "generativelanguage.googleapis.com/generate_content_free_tier_requests",
) -> dict:
    """The error envelope Gemini actually returns on a 429.

    Shaped from the message in the bug report: a QuotaFailure naming the metric
    and the quota id, and a RetryInfo carrying a protobuf Duration.
    """
    details: list[dict] = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaMetric": metric, "quotaId": quota_id, "quotaValue": "20"}],
        }
    ]
    if retry_delay is not None:
        details.append(
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
        )
    return {
        "error": {
            "code": 429,
            "message": "You exceeded your current quota. Limit: 20",
            "status": "RESOURCE_EXHAUSTED",
            "details": details,
        }
    }


class StubRateLimitError(Exception):
    """Mimics the SDK's 429, including the fields the provider reads.

    Deliberately NOT a subclass of any SDK error class. The provider identifies
    a failure by the status it carries, not by where its class lives, and this
    stub is what proves that promise holds without importing a private module.
    """

    def __init__(self, body: dict | None = None, headers: dict | None = None) -> None:
        super().__init__("429 RESOURCE_EXHAUSTED")
        self.status_code = 429
        self.message = "You exceeded your current quota. Limit: 20"
        self.body = body if body is not None else quota_body()
        if headers is not None:
            self.response = httpx.Response(429, headers=headers)


class CountingInteractions:
    """Counts create() calls and replays a scripted sequence of outcomes."""

    def __init__(self, outcomes: list) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StubInteraction:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.status = "completed"
        self.errors = []


class StubClient:
    def __init__(self, interactions) -> None:
        self.interactions = interactions


def provider_with(outcomes: list) -> tuple[GeminiLLMProvider, CountingInteractions]:
    """A real provider (constructor runs) wired to a counting stub client."""
    p = GeminiLLMProvider(api_key="test-key-not-real")
    interactions = CountingInteractions(outcomes)
    p._client = StubClient(interactions)
    return p, interactions


@pytest.fixture(autouse=True)
def no_real_sleeping(monkeypatch):
    """Record waits instead of taking them, so a 44-second test runs instantly.

    The recorded values are asserted on: a test that silently skipped the wait
    could not tell a correct delay from a wrong one.
    """
    slept: list[float] = []
    monkeypatch.setattr(
        "src.rag.llm.gemini_provider.time.sleep", lambda seconds: slept.append(seconds)
    )
    return slept


def ask(p: GeminiLLMProvider):
    return p.generate_structured(system="s", prompt="p", output_model=Tiny)


OK = StubInteraction('{"answer": "fine"}')


# --------------------------------------------------------------------------- #
# 1. The SDK is stopped from retrying 429 behind our back
# --------------------------------------------------------------------------- #


class TestSdkRetryIsDisarmed:
    def test_429_is_not_in_the_sdk_retryable_set(self) -> None:
        """The whole quota problem in miniature.

        Left at its default the generated client retries 429 with
        max_retries=3, so one rate-limited analysis fires up to twelve
        requests against a twenty-request allowance. This asserts against the
        client the provider actually built, not against our own constant, so
        an SDK upgrade that ignores the option fails here rather than in
        production.
        """
        p = GeminiLLMProvider(api_key="test-key-not-real")
        config = p._client.interactions.sdk_configuration.retry_config

        assert config.status_codes_override is not None, "SDK left on its default set"
        assert "429" not in config.status_codes_override
        assert "5XX" not in config.status_codes_override

    def test_transient_server_faults_are_still_retried_once(self) -> None:
        """Removing 429 must not disarm the retry that genuinely helps.

        Production logs show a 500 mid-analysis being retried and succeeding.
        That behaviour is worth keeping: it costs nothing when it works, and
        a 5xx is not a quota.
        """
        p = GeminiLLMProvider(api_key="test-key-not-real")
        config = p._client.interactions.sdk_configuration.retry_config

        assert "500" in config.status_codes_override
        assert config.max_retries == 1, "one retry, not the default three"


# --------------------------------------------------------------------------- #
# 2. Parsing what the provider told us
# --------------------------------------------------------------------------- #


class TestRetryDelayParsing:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("44s", 44.0), ("1.5s", 1.5), ("0s", 0.0), (" 12s ", 12.0), (30, 30.0)],
    )
    def test_retry_delay_is_read_from_the_response_body(self, value, expected) -> None:
        """This is the field the SDK's own backoff never looks at.

        Gemini puts the delay in a RetryInfo detail inside the body. The
        generated retry layer reads only the Retry-After header, which is why
        it slept half a second when the API had asked for forty-four.
        """
        assert _retry_delay_from_body(quota_body(retry_delay=value)) == expected

    def test_a_body_without_retry_info_yields_no_delay(self) -> None:
        """None means "not stated", and must never become a default.

        A guessed delay would be shown to the user as a countdown, which
        states something the API did not.
        """
        assert _retry_delay_from_body(quota_body(retry_delay=None)) is None

    def test_an_unwrapped_error_object_is_also_understood(self) -> None:
        """Both envelope shapes appear in the wild depending on the layer that
        parsed the reply, so neither may be the only one handled."""
        inner = quota_body()["error"]
        assert _retry_delay_from_body(inner) == 44.0

    def test_garbage_bodies_do_not_raise(self) -> None:
        """A malformed error payload is still an error; it must not become a
        crash on top of the failure it was describing."""
        for junk in [None, "", 5, [], {"error": "text"}, {"details": "no"}]:
            assert _retry_delay_from_body(junk) is None


class TestRetryAfterHeader:
    def test_retry_after_header_is_used_when_the_body_is_silent(self) -> None:
        error = StubRateLimitError(body=quota_body(retry_delay=None), headers={"Retry-After": "17"})
        translated = GeminiLLMProvider._translate(error)
        assert translated.retry_after_seconds == 17.0

    def test_retry_after_ms_header_is_converted_to_seconds(self) -> None:
        error = StubRateLimitError(
            body=quota_body(retry_delay=None), headers={"retry-after-ms": "2500"}
        )
        assert GeminiLLMProvider._translate(error).retry_after_seconds == 2.5

    def test_the_body_wins_over_the_header(self) -> None:
        """Both sources present: prefer the body.

        The RetryInfo is quota-specific, while Retry-After can be set by any
        intermediary. Preferring the more specific one is why this ordering is
        pinned rather than left to chance.
        """
        error = StubRateLimitError(body=quota_body(retry_delay="44s"), headers={"Retry-After": "1"})
        assert GeminiLLMProvider._translate(error).retry_after_seconds == 44.0

    def test_a_missing_response_object_is_not_an_error(self) -> None:
        error = StubRateLimitError(body=quota_body(retry_delay=None))
        assert GeminiLLMProvider._translate(error).retry_after_seconds is None


# --------------------------------------------------------------------------- #
# 3. Temporary versus spent
# --------------------------------------------------------------------------- #


class TestClassification:
    def test_a_per_minute_limit_is_reported_as_temporary(self) -> None:
        error = GeminiLLMProvider._translate(StubRateLimitError())
        assert isinstance(error, LLMRateLimitError)
        assert error.quota_exhausted is False
        assert error.retry_after_seconds == 44.0
        assert "temporarily rate limiting" in str(error)

    def test_a_per_day_quota_is_reported_as_exhausted(self) -> None:
        """The distinction that stops the interface lying.

        A spent daily free tier does not come back in forty-four seconds, and
        telling the user to "retry shortly" spends what little is left.
        """
        body = quota_body(quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        error = GeminiLLMProvider._translate(StubRateLimitError(body=body))
        assert error.quota_exhausted is True
        assert "exhausted" in str(error)

    def test_a_very_long_delay_is_treated_as_exhausted(self) -> None:
        """An hour-long wait is a long window by any other name, whatever the
        quota id happens to be called."""
        body = quota_body(retry_delay="3600s", quota_id="SomethingUnfamiliar")
        assert GeminiLLMProvider._translate(StubRateLimitError(body=body)).quota_exhausted is True

    def test_an_unlabelled_limit_is_not_claimed_to_be_exhausted(self) -> None:
        """No evidence is not evidence of exhaustion.

        `quota_exhausted` is a claim about the account, and this code has no
        grounds for it here. It says so rather than guessing in either
        direction, and the message admits the duration is unknown.
        """
        body = {"error": {"code": 429, "message": "Too many requests", "details": []}}
        error = GeminiLLMProvider._translate(StubRateLimitError(body=body))
        assert error.quota_exhausted is False
        assert error.retry_after_seconds is None
        assert "did not say for how long" in str(error)

    def test_the_provider_message_is_kept_not_replaced(self) -> None:
        """Google's own sentence names which limit was hit, which is more use
        to whoever has to fix it than our generic wording alone."""
        assert "Limit: 20" in str(GeminiLLMProvider._translate(StubRateLimitError()))

    @pytest.mark.parametrize(
        "quota_id",
        ["GenerateRequestsPerDayPerProjectPerModel-FreeTier", "requests_per_day", "PER-DAY-limit"],
    )
    def test_per_day_is_recognised_however_it_is_spelled(self, quota_id) -> None:
        assert _looks_exhausted(quota_body(quota_id=quota_id), "", None) is True

    def test_a_rate_limit_never_leaks_configuration(self) -> None:
        """The message reaches the browser verbatim, so it must carry nothing
        but the provider's own words."""
        text = str(GeminiLLMProvider._translate(StubRateLimitError()))
        for secret in ["test-key-not-real", "apikey", "Authorization", "GEMINI_API_KEY="]:
            assert secret not in text


# --------------------------------------------------------------------------- #
# 4. At most one retry, and often none
# --------------------------------------------------------------------------- #


class TestRetryRestraint:
    def test_a_short_limit_is_retried_exactly_once_and_succeeds(self, no_real_sleeping) -> None:
        p, calls = provider_with([StubRateLimitError(), OK])
        assert ask(p).answer == "fine"
        assert calls.calls == 2, "one original request plus one retry"
        assert no_real_sleeping == [44.0], "waited the time the API asked for"

    def test_a_second_rate_limit_is_final(self, no_real_sleeping) -> None:
        """The retry is not a loop. Two 429s in a row means two requests
        total, then a raised error - never a third attempt."""
        p, calls = provider_with([StubRateLimitError(), StubRateLimitError()])
        with pytest.raises(LLMRateLimitError):
            ask(p)
        assert calls.calls == 2
        assert len(no_real_sleeping) == 1

    def test_an_exhausted_quota_is_never_retried(self, no_real_sleeping) -> None:
        """The single most important assertion in this file.

        A retry cannot succeed against a spent allowance, and firing one
        anyway is what turned a limit into a longer outage.
        """
        body = quota_body(quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        p, calls = provider_with([StubRateLimitError(body=body), OK])
        with pytest.raises(LLMRateLimitError) as raised:
            ask(p)
        assert raised.value.quota_exhausted is True
        assert calls.calls == 1, "no retry against an exhausted quota"
        assert no_real_sleeping == []

    def test_a_limit_with_no_stated_delay_is_not_retried(self, no_real_sleeping) -> None:
        """Retrying without a delay means picking one, and any number we pick
        is a guess that costs a request when it is wrong."""
        p, calls = provider_with([StubRateLimitError(body=quota_body(retry_delay=None)), OK])
        with pytest.raises(LLMRateLimitError):
            ask(p)
        assert calls.calls == 1

    def test_a_delay_longer_than_the_cap_is_not_waited_out(self, no_real_sleeping) -> None:
        """A request already holds a serverless function open. Past the cap the
        honest answer is to report the wait, not to sit through it."""
        long_wait = f"{int(MAX_RETRY_WAIT_SECONDS) + 30}s"
        body = quota_body(retry_delay=long_wait, quota_id="ShortWindowButSlow")
        p, calls = provider_with([StubRateLimitError(body=body), OK])
        with pytest.raises(LLMRateLimitError):
            ask(p)
        assert calls.calls == 1
        assert no_real_sleeping == []

    def test_the_waiting_budget_is_shared_across_one_analysis(self, no_real_sleeping) -> None:
        """Three passes must not each be free to sit out the full cap.

        The provider is built once per request, so the budget is per analysis.
        Without this a rate-limited paper could wait three minutes and still
        fail, overrunning the platform's request ceiling.
        """
        near_budget = f"{int(RATE_LIMIT_WAIT_BUDGET_SECONDS)}s"
        body = quota_body(retry_delay=near_budget, quota_id="ShortWindow")
        p, calls = provider_with(
            [StubRateLimitError(body=body), OK, StubRateLimitError(body=body), OK]
        )

        assert ask(p).answer == "fine"  # spends the whole budget
        assert calls.calls == 2

        with pytest.raises(LLMRateLimitError):
            ask(p)  # budget gone, so no wait and no retry
        assert calls.calls == 3
        assert len(no_real_sleeping) == 1

    def test_a_non_rate_limit_failure_is_not_retried_here(self, no_real_sleeping) -> None:
        """Only rate limits get the wait. Anything else keeps its existing
        behaviour, which is to fail on the first attempt."""

        class Boom(Exception):
            status_code = 500
            message = "server error"

        p, calls = provider_with([Boom(), OK])
        with pytest.raises(LLMError):
            ask(p)
        assert calls.calls == 1

    def test_generate_text_gets_the_same_restraint(self, no_real_sleeping) -> None:
        """The long-paper digest pass runs through generate_text, and a paper
        long enough to need it makes the most calls of all."""
        body = quota_body(quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        p, calls = provider_with([StubRateLimitError(body=body), OK])
        with pytest.raises(LLMRateLimitError):
            p.generate_text(system="s", prompt="p")
        assert calls.calls == 1


# --------------------------------------------------------------------------- #
# 5. The HTTP contract
# --------------------------------------------------------------------------- #


def upload(client):
    return client.post(
        "/api/analyze",
        files={"file": ("paper.pdf", build_text_pdf(PAPER_TEXT), "application/pdf")},
    )


def client_failing_with(error: Exception) -> TestClient:
    app.dependency_overrides[get_provider] = lambda: FakeLLMProvider(fail_with=error)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    return TestClient(app)


class TestHttpStatus:
    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_a_rate_limit_is_429_and_not_502(self) -> None:
        """502 says the upstream is broken. It is not: it is working and we
        are over an allowance. The frontend keys its wording on this."""
        response = upload(
            client_failing_with(LLMRateLimitError("slow down", retry_after_seconds=44))
        )
        assert response.status_code == 429
        assert response.status_code != 502

    def test_retry_after_is_sent_when_the_provider_stated_one(self) -> None:
        response = upload(client_failing_with(LLMRateLimitError("wait", retry_after_seconds=44)))
        assert response.headers["retry-after"] == "44"

    def test_a_fractional_delay_is_rounded_up_never_down(self) -> None:
        """Rounding down would have the client retry fractionally early,
        straight back into the limit it was waiting out."""
        response = upload(client_failing_with(LLMRateLimitError("wait", retry_after_seconds=1.2)))
        assert response.headers["retry-after"] == "2"

    def test_no_retry_after_header_when_none_was_supplied(self) -> None:
        """An absent header means "unknown". Sending a made-up number would
        have the interface count down to a moment nobody promised."""
        response = upload(client_failing_with(LLMRateLimitError("rate limited")))
        assert "retry-after" not in response.headers

    def test_exhaustion_is_flagged_for_the_interface(self) -> None:
        error = LLMRateLimitError("gone", quota_exhausted=True)
        response = upload(client_failing_with(error))
        assert response.headers["x-quota-exhausted"] == "true"

    def test_a_temporary_limit_is_not_flagged_as_exhausted(self) -> None:
        error = LLMRateLimitError("slow down", retry_after_seconds=10)
        assert "x-quota-exhausted" not in upload(client_failing_with(error)).headers

    def test_the_response_body_carries_the_explanation(self) -> None:
        response = upload(
            client_failing_with(LLMRateLimitError("quota spent", quota_exhausted=True))
        )
        assert response.json()["detail"] == "quota spent"

    def test_an_ordinary_generation_failure_is_still_502(self) -> None:
        """The new branch must not swallow the old one: everything that was a
        502 before is a 502 still."""
        assert upload(client_failing_with(LLMError("model exploded"))).status_code == 502

    def test_the_rate_limit_headers_expose_no_configuration(self) -> None:
        error = LLMRateLimitError("wait", retry_after_seconds=44, quota_exhausted=True)
        headers = upload(client_failing_with(error)).headers
        assert set(k.lower() for k in headers) & {"retry-after", "x-quota-exhausted"}
        for name in headers:
            assert "key" not in name.lower()
            assert "supabase" not in name.lower()


# --------------------------------------------------------------------------- #
# 6. Nothing that worked before has changed
# --------------------------------------------------------------------------- #


class TestSuccessUnchanged:
    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_a_successful_analysis_still_makes_exactly_three_calls(self) -> None:
        """The three passes stay three passes. Rate-limit handling was not
        allowed to quietly consolidate or reorder them."""
        fake = FakeLLMProvider()
        app.dependency_overrides[get_provider] = lambda: fake
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)

        response = upload(TestClient(app))

        assert response.status_code == 200
        assert len(fake.structured_calls) == 3
        body = response.json()
        assert body["summary"] and body["research_gaps"] and body["literature_review"]

    def test_a_successful_call_never_waits(self, no_real_sleeping) -> None:
        p, calls = provider_with([OK])
        assert ask(p).answer == "fine"
        assert calls.calls == 1
        assert no_real_sleeping == []
