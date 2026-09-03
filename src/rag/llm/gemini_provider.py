"""Google Gemini implementation of `LLMProvider`.

Default model: `gemini-3.7-flash`, the latest stable Flash model, chosen
because a Vercel function has a 300-second ceiling and a Flash-tier model with
`thinking_level` turned up finishes a three-call analysis comfortably inside it.
`LLM_MODEL` overrides it, so switching to `gemini-2.5-pro` for deeper reasoning
is one environment variable and no code change.

This file is the ONLY place Google SDK types appear. Everything else in the
codebase speaks in terms of `LLMProvider`, `LLMError`, and Pydantic models,
the same rule `anthropic_provider.py` follows.

WHY `response_format` WITH A JSON SCHEMA
----------------------------------------
Passing `Model.model_json_schema()` constrains the model to our schema, so the
reply is JSON we can validate rather than prose or a markdown-fenced object
that needs regex repair. It is the Gemini equivalent of Anthropic's
`messages.parse`, and it is what lets `generate_structured` promise either a
valid object or an exception, never a half-filled one.

Validation still happens here with `model_validate_json`. The schema constrains
the model; it does not make the SDK hand back a typed instance.

WHY THE STATUS IS CHECKED
-------------------------
A truncated reply is the dangerous failure: it arrives as a 200 with valid-
looking JSON that is missing content. `interaction.status` distinguishes a
finished answer from one cut off at the token limit, so we reject rather than
silently analyse a paper on half a response.

RATE LIMITING, AND WHY THE SDK IS TOLD TO STOP RETRYING
-------------------------------------------------------
`client.interactions.create` does NOT use the retry settings on
`google.genai`'s own client. It is routed through the generated `_gaos` layer,
which builds its own retry policy from `HttpOptions.retry_options` and, left
alone, retries `408, 409, 429, 5XX` with `max_retries=3` - four attempts.

That default is actively harmful here. A paper is three sequential calls, so
one rate-limited analysis could fire twelve requests against a free tier that
allows twenty per window, turning a brief limit into an exhausted one. Worse,
those retries are blind: the `_gaos` backoff reads the `Retry-After` HEADER but
never the `retryDelay` that Gemini actually puts in the 429 BODY, so it sleeps
half a second and tries again when the API asked for forty.

`_RETRY_OPTIONS` therefore removes 429 from the SDK's retryable set entirely
and leaves it one retry for genuine transient server faults (a 500 mid-analysis
is real and recoverable; production logs show one). Rate limiting is handled
one level up instead, in `_call_with_rate_limit_retry`, which can read the body,
tell a one-minute limit apart from a spent daily allowance, and wait the length
the API asked for - at most once, and never beyond a fixed budget.

The result is fewer requests per rate-limited analysis, not more: two per pass
in the worst case, against the SDK default's four.
"""

import logging
import re
import time
from typing import Any, TypeVar

import httpx
from google import genai
from google.genai.types import HttpOptions, HttpRetryOptions
from pydantic import BaseModel, ValidationError

from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gemini-3.7-flash"

# `LLM_EFFORT` uses the project's own vocabulary (shared with the Anthropic
# provider, which accepts up to "max"). Gemini's `thinking_level` stops at
# "high", so the two levels above it map down rather than being rejected:
# asking for more thought than a vendor offers should get you its maximum, not
# an error. Confining the mapping here is what keeps `LLM_EFFORT` portable.
_THINKING_LEVEL_BY_EFFORT: dict[str, str] = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}
_DEFAULT_THINKING_LEVEL = "high"

# Statuses that are NOT a complete answer, and the reason to report for each.
# `incomplete` is the token-limit case; `budget_exceeded` is an account limit,
# which is an operator problem rather than the uploader's.
_FAILED_STATUS_REASONS: dict[str, str] = {
    "incomplete": (
        "The model's response was cut off before it finished. The paper may be "
        "too dense to analyse in one pass."
    ),
    "failed": "The model failed to produce a response.",
    "cancelled": "The request was cancelled before the model finished.",
    "budget_exceeded": (
        "The configured Gemini project has exhausted its budget or quota. This "
        "needs an operator, not a different file."
    ),
}


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

# What the SDK is allowed to retry on its own. 429 is deliberately ABSENT:
# retrying a quota failure blindly is what turns a temporary limit into an
# exhausted one, and the layer below cannot read the delay the API supplied.
# 5xx and 408 stay, with a single retry, because those are genuine transient
# faults that a second attempt fixes without costing quota when it succeeds.
_SDK_RETRY_STATUS_CODES = [408, 500, 502, 503, 504]

# One RETRY, not one attempt. `HttpRetryOptions.attempts` is documented as
# "maximum number of attempts, including the original request", but the
# generated layer assigns it straight to `max_retries`, which its loop counts
# as retries AFTER the first try. So 1 here means two requests at most, and 2
# would mean three. The value is asserted against the constructed client in
# tests/test_rate_limit.py rather than trusted to this comment.
_SDK_RETRY_ATTEMPTS = 1

_RETRY_OPTIONS = HttpRetryOptions(
    attempts=_SDK_RETRY_ATTEMPTS,
    http_status_codes=_SDK_RETRY_STATUS_CODES,
)

# The longest we will ever sit and wait for a rate limit to clear. A request
# already holds a serverless function open, and a wait longer than this is
# better spent telling the user when to come back.
MAX_RETRY_WAIT_SECONDS = 60.0

# Total waiting allowed across ONE analysis. The provider is built per request,
# so this instance attribute is naturally per-analysis: three passes cannot
# each sit out a minute and push the request past the platform's ceiling.
RATE_LIMIT_WAIT_BUDGET_SECONDS = 60.0

# A retry delay longer than this is not something to wait out mid-request; it
# indicates a long window (typically a daily allowance) rather than a burst
# limit, and is reported as exhausted so the user is told to come back later
# instead of being made to watch a countdown that will not finish.
_LONG_WINDOW_DELAY_SECONDS = 120.0

# `retryDelay` arrives as a protobuf Duration string: "44s", "1.5s", "0s".
_DURATION_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*s\s*$")


def _as_seconds(value: Any) -> float | None:
    """Parse a protobuf Duration ("44s") or a plain number of seconds."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    if isinstance(value, str):
        match = _DURATION_RE.match(value)
        if match:
            return float(match.group(1))
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _error_body(exc: BaseException) -> Any:
    """The parsed error payload, from either SDK error hierarchy.

    The private `_gaos` errors carry it as `body`; the public
    `google.genai.errors.APIError` carries it as `details`. Read whichever is
    present, for the same reason `_status_code_of` reads either status field:
    identify the failure by what it holds, not by which private module its
    class happens to live in this release.
    """
    for attribute in ("body", "details"):
        value = getattr(exc, attribute, None)
        if isinstance(value, (dict, list)):
            return value
    return None


def _iter_detail_entries(body: Any) -> list[dict[str, Any]]:
    """The `error.details` list from a Google API error payload.

    Tolerates the two shapes seen in practice: the full envelope
    `{"error": {"details": [...]}}` and the already-unwrapped `{"details": [...]}`.
    """
    if isinstance(body, list):
        entries: list[dict[str, Any]] = []
        for item in body:
            entries.extend(_iter_detail_entries(item))
        return entries
    if not isinstance(body, dict):
        return []
    inner = body.get("error")
    if isinstance(inner, dict):
        body = inner
    details = body.get("details")
    if not isinstance(details, list):
        return []
    return [entry for entry in details if isinstance(entry, dict)]


def _retry_delay_from_body(body: Any) -> float | None:
    """Gemini's own `RetryInfo.retryDelay`, in seconds, if it sent one.

    This is the field the SDK's backoff ignores. It is the most accurate
    timing available, which is why it is read before falling back to headers.
    """
    for entry in _iter_detail_entries(body):
        delay = _as_seconds(entry.get("retryDelay") or entry.get("retry_delay"))
        if delay is not None:
            return delay
    return None


def _retry_delay_from_headers(exc: BaseException) -> float | None:
    """`Retry-After` / `retry-after-ms`, when the response is reachable.

    Both spellings are checked because the two SDK hierarchies attach the
    response differently and Google sends either depending on the endpoint.
    """
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        after_ms = headers.get("retry-after-ms")
        after = headers.get("retry-after")
    except Exception:  # noqa: BLE001 - a hostile headers object is not worth a crash
        return None
    if after_ms is not None:
        seconds = _as_seconds(after_ms)
        if seconds is not None:
            return seconds / 1000.0
    return _as_seconds(after) if after is not None else None


def _looks_exhausted(body: Any, message: str, delay: float | None) -> bool:
    """Whether there is POSITIVE evidence of a long, spent allowance.

    Returning False means only "no such evidence found". It never means the
    limit has been proven temporary, and nothing downstream may read it that
    way: an unlabelled 429 is reported as a rate limit of unknown length, which
    is what we actually know.

    Two signals count. A quota id naming a per-day window is conclusive - a
    daily free-tier allowance does not come back in a minute. A retry delay
    beyond `_LONG_WINDOW_DELAY_SECONDS` says the same thing in different words.
    """
    if delay is not None and delay > _LONG_WINDOW_DELAY_SECONDS:
        return True

    haystacks: list[str] = []
    for entry in _iter_detail_entries(body):
        violations = entry.get("violations")
        if isinstance(violations, list):
            for violation in violations:
                if isinstance(violation, dict):
                    haystacks.append(str(violation.get("quotaId") or ""))
                    haystacks.append(str(violation.get("quota_id") or ""))
    haystacks.append(message)

    return any("perday" in text.lower().replace("_", "").replace("-", "") for text in haystacks)


def _rate_limit_error(exc: BaseException) -> LLMRateLimitError:
    """Build the project's rate-limit error from a Gemini 429.

    The message is written for the person who has to act on it, and says only
    what was actually established. It never carries the API key, the request
    headers, or any environment value: the inputs are the response body, the
    response headers, and the API's own sentence.
    """
    body = _error_body(exc)
    message = _message_of(exc)
    # The body is the more accurate source; the header is the fallback. The
    # SDK's own backoff uses only the header, which is why a body-only delay
    # is exactly the case that was being ignored.
    delay = _retry_delay_from_body(body)
    if delay is None:
        delay = _retry_delay_from_headers(exc)
    exhausted = _looks_exhausted(body, message, delay)

    if exhausted:
        text = (
            "The Gemini API quota for this key has been exhausted. This is a "
            "limit on the account, not a problem with the paper, and it will "
            "not clear by trying again now. Wait for the quota to reset, or "
            "raise the limit on the Google AI Studio project."
        )
    elif delay is not None:
        text = (
            "The Gemini API is temporarily rate limiting requests. It asked to "
            f"be retried in about {delay:.0f} seconds."
        )
    else:
        text = (
            "The Gemini API is temporarily rate limiting requests and did not "
            "say for how long. Please wait a little and try again."
        )

    if message:
        # The API's own wording names which limit was hit, which is more use to
        # an operator than our sentence alone. Appended, never substituted.
        text = f"{text} Details: {message}"

    return LLMRateLimitError(
        text,
        retry_after_seconds=delay,
        quota_exhausted=exhausted,
    )


def _status_code_of(exc: BaseException) -> int | None:
    """The HTTP status an SDK exception carries, from either error hierarchy.

    `status_code` is what the private interactions errors use; `code` is what
    the public `google.genai.errors.APIError` uses. Anything else - including a
    connection failure, which never got a response - has neither.
    """
    for attribute in ("status_code", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _message_of(exc: BaseException) -> str:
    message = getattr(exc, "message", None)
    return message if isinstance(message, str) and message else str(exc)


def _caused_by(exc: BaseException, kind: type[BaseException]) -> bool:
    """Whether `exc`, or anything it was raised from, is a `kind`.

    The SDK re-raises httpx failures as its own connection classes with
    `raise ... from exc`, so the useful identity is on the cause, not the
    exception that surfaces. The chain is walked with a depth cap because a
    malformed chain must not hang the request.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen and len(seen) < 10:
        if isinstance(current, kind):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def thinking_level_for_effort(effort: str) -> str:
    """Translate `LLM_EFFORT` into Gemini's `thinking_level`.

    Exposed (rather than kept private) because it encodes a real decision, how
    "max" degrades on a vendor that has no such level, and a decision worth
    making is worth testing directly.
    """
    return _THINKING_LEVEL_BY_EFFORT.get(effort.strip().lower(), _DEFAULT_THINKING_LEVEL)


class GeminiLLMProvider(LLMProvider):
    """Text generation backed by the Gemini API's Interactions endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = 16_000,
        effort: str = "high",
        timeout_seconds: float = 600.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMCredentialsError(
                "GEMINI_API_KEY is not set. ResearchForge cannot analyse a "
                "paper without it. Get a key from https://aistudio.google.com/apikey "
                "and put it in .env (never in source code)."
            )
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._effort = effort
        self._thinking_level = thinking_level_for_effort(effort)
        # Analysing a long paper legitimately takes minutes, so the timeout is
        # generous rather than the SDK's shorter default.
        self._timeout_seconds = timeout_seconds
        # Waiting is budgeted per provider instance, and the provider is built
        # once per request, so the three passes of one analysis share a single
        # budget rather than each being free to sit out a minute.
        self._wait_budget = RATE_LIMIT_WAIT_BUDGET_SECONDS
        self._client = genai.Client(
            api_key=api_key,
            # Takes 429 away from the SDK's blind retry. See the module
            # docstring: this REDUCES requests, it does not add them.
            http_options=HttpOptions(retry_options=_RETRY_OPTIONS),
        )

    @property
    def model_name(self) -> str:
        return self._model

    # ---------- shared request plumbing ----------

    def _base_kwargs(self, system: str, prompt: str) -> dict[str, Any]:
        return {
            "model": self._model,
            "system_instruction": system,
            "input": prompt,
            "generation_config": {
                "max_output_tokens": self._max_output_tokens,
                # How hard the model thinks. Analytical work earns a high level;
                # tests and smoke runs turn it down through LLM_EFFORT.
                "thinking_level": self._thinking_level,
            },
            "timeout": self._timeout_seconds,
        }

    @staticmethod
    def _translate(exc: Exception) -> LLMError:
        """Map an SDK exception onto a project-owned error.

        Ordered most-specific first, so a 401 is never reported as a generic
        API failure. The API layer maps `LLMCredentialsError` to a 503 and the
        rest to a 502, which is why the distinction has to survive this
        translation rather than collapsing into one message.

        WHY THIS MATCHES ON A STATUS CODE, NOT AN EXCEPTION CLASS
        ---------------------------------------------------------
        `client.interactions` raises from `google.genai._gaos.lib.compat_errors`,
        a PRIVATE module whose `APIError` is a different class from the public
        `google.genai.errors.APIError` that `client.models` raises. Matching on
        class identity therefore silently missed every interactions error - a
        rejected key included, which turned an honest 503 into a misleading 502.
        Importing the private class would fix the symptom and re-break on the
        next SDK reshuffle.

        Both hierarchies expose the HTTP status (`status_code` on the private
        one, `code` on the public one) and a `message`. Reading whichever is
        present identifies the failure by what it IS rather than by where its
        class happens to live this release.
        """
        status = _status_code_of(exc)
        if status is not None:
            if status in (401, 403):
                return LLMCredentialsError(
                    "The Gemini API rejected the configured key, or it lacks "
                    "access to this model. Check GEMINI_API_KEY."
                )
            if status == 429:
                return _rate_limit_error(exc)
            return LLMError(f"The Gemini API returned an error: {_message_of(exc)}")

        # No status code: the request never completed. The SDK wraps httpx
        # failures in its own connection classes, so the original is looked for
        # along the __cause__ chain as well as on the exception itself.
        if _caused_by(exc, httpx.TimeoutException):
            return LLMError(
                "The analysis timed out. This paper may be unusually long - "
                "try again, or upload a shorter document."
            )
        if _caused_by(exc, httpx.RequestError):
            return LLMError("Could not reach the Gemini API. Check network connectivity.")
        return LLMError(f"Unexpected generation failure: {exc}")

    def _call_with_rate_limit_retry(self, send: Any) -> Any:
        """Run one Gemini call, retrying a SHORT rate limit at most once.

        The whole point of this method is restraint. It retries when, and only
        when, all four of these hold:

          1. the failure was a rate limit, not anything else;
          2. nothing indicates a long or spent allowance;
          3. the API told us how long to wait, so the wait is its number and
             not our guess;
          4. that wait fits inside the cap AND inside the budget left for this
             analysis.

        Any of those failing means the error is raised immediately. In
        particular an exhausted quota is never retried: a second request cannot
        succeed and would spend allowance that has already run out.

        One retry, never two. There is no loop here on purpose.
        """
        try:
            return send()
        except LLMError:
            raise
        except Exception as exc:
            error = self._translate(exc)
            if not isinstance(error, LLMRateLimitError):
                raise error from exc

            wait = error.retry_after_seconds
            if (
                error.quota_exhausted
                or wait is None
                or wait > MAX_RETRY_WAIT_SECONDS
                or wait > self._wait_budget
            ):
                logger.warning(
                    "gemini rate limited, not retrying (exhausted=%s, retry_after=%s)",
                    error.quota_exhausted,
                    wait,
                )
                raise error from exc

            # Charged whether or not the retry succeeds, so a pass that waits
            # cannot be followed by two more passes that each wait again.
            self._wait_budget -= wait
            logger.info("gemini rate limited, waiting %.0fs for the single retry", wait)
            time.sleep(wait)

        # Outside the except block: this is the one retry, and a rate limit
        # here is final. Raising from here rather than recursing is what makes
        # "at most once" a property of the code's shape, not of a counter.
        try:
            return send()
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

    @staticmethod
    def _check_status(interaction: Any) -> None:
        """Reject anything that is not a finished answer.

        A cut-off response is the failure worth catching: it looks like success
        and is missing content, so using it would mean analysing a paper on a
        partial reply without anyone noticing.
        """
        status = getattr(interaction, "status", None)
        status = getattr(status, "value", status)  # tolerate an enum or a str
        if status is None:
            return
        reason = _FAILED_STATUS_REASONS.get(str(status))
        if reason is None:
            return

        # The API's own error text, when it gave any, is more specific than
        # ours - so append it rather than discarding it.
        details = ""
        api_errors = getattr(interaction, "errors", None) or []
        messages = [m for m in (getattr(e, "message", None) for e in api_errors) if m]
        if messages:
            details = f" ({'; '.join(messages)})"
        raise LLMResponseError(f"{reason}{details}")

    @staticmethod
    def _output_text(interaction: Any) -> str:
        text = (getattr(interaction, "output_text", None) or "").strip()
        if not text:
            raise LLMResponseError("The model returned an empty response.")
        return text

    # ---------- interface ----------

    def generate_structured(self, *, system: str, prompt: str, output_model: type[T]) -> T:
        interaction = self._call_with_rate_limit_retry(
            lambda: self._client.interactions.create(
                **self._base_kwargs(system, prompt),
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    # Pydantic emits `additionalProperties: false` here because
                    # the schemas set extra="forbid" - so the model cannot
                    # invent fields we would then ignore.
                    "schema": output_model.model_json_schema(),
                },
            )
        )

        self._check_status(interaction)
        text = self._output_text(interaction)

        try:
            return output_model.model_validate_json(text)
        except ValidationError as exc:
            # The schema constrains the model; it does not guarantee the reply.
            # A mismatch surfaces here as a clear error rather than a confusing
            # one downstream.
            raise LLMResponseError(
                f"The model's output did not match the expected schema: {exc}"
            ) from exc

    def generate_text(self, *, system: str, prompt: str) -> str:
        interaction = self._call_with_rate_limit_retry(
            lambda: self._client.interactions.create(**self._base_kwargs(system, prompt))
        )

        self._check_status(interaction)
        return self._output_text(interaction)

    def __repr__(self) -> str:
        """Redacted repr - must never expose the API key in logs or tracebacks."""
        return (
            f"GeminiLLMProvider(model={self._model!r}, "
            f"effort={self._effort!r}, api_key='***redacted***')"
        )
