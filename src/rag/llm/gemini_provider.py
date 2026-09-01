"""Google Gemini implementation of `LLMProvider`.

Default model: `gemini-3.7-flash` — the latest stable Flash model, chosen
because a Vercel function has a 300-second ceiling and a Flash-tier model with
`thinking_level` turned up finishes a three-call analysis comfortably inside it.
`LLM_MODEL` overrides it, so switching to `gemini-2.5-pro` for deeper reasoning
is one environment variable and no code change.

This file is the ONLY place Google SDK types appear. Everything else in the
codebase speaks in terms of `LLMProvider`, `LLMError`, and Pydantic models —
the same rule `anthropic_provider.py` follows.

WHY `response_format` WITH A JSON SCHEMA
----------------------------------------
Passing `Model.model_json_schema()` constrains the model to our schema, so the
reply is JSON we can validate rather than prose or a markdown-fenced object
that needs regex repair. It is the Gemini equivalent of Anthropic's
`messages.parse`, and it is what lets `generate_structured` promise either a
valid object or an exception — never a half-filled one.

Validation still happens here with `model_validate_json`. The schema constrains
the model; it does not make the SDK hand back a typed instance.

WHY THE STATUS IS CHECKED
-------------------------
A truncated reply is the dangerous failure: it arrives as a 200 with valid-
looking JSON that is missing content. `interaction.status` distinguishes a
finished answer from one cut off at the token limit, so we reject rather than
silently analyse a paper on half a response.
"""

import logging
from typing import Any, TypeVar

import httpx
from google import genai
from pydantic import BaseModel, ValidationError

from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMResponseError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gemini-3.7-flash"

# `LLM_EFFORT` uses the project's own vocabulary (shared with the Anthropic
# provider, which accepts up to "max"). Gemini's `thinking_level` stops at
# "high", so the two levels above it map down rather than being rejected —
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

    Exposed (rather than kept private) because it encodes a real decision — how
    "max" degrades on a vendor that has no such level — and a decision worth
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
        self._client = genai.Client(api_key=api_key)

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
                # Quota, not a fault. The API's own text names which limit was
                # hit and often how long to wait, which is more use to an
                # operator than our generic sentence, so it is kept.
                return LLMError(
                    "The Gemini API is rate limiting this key - the request "
                    f"exceeded a quota. Please retry shortly. Details: {_message_of(exc)}"
                )
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
        try:
            interaction = self._client.interactions.create(
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
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

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
        try:
            interaction = self._client.interactions.create(**self._base_kwargs(system, prompt))
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        self._check_status(interaction)
        return self._output_text(interaction)

    def __repr__(self) -> str:
        """Redacted repr - must never expose the API key in logs or tracebacks."""
        return (
            f"GeminiLLMProvider(model={self._model!r}, "
            f"effort={self._effort!r}, api_key='***redacted***')"
        )
