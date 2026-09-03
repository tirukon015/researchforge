"""Anthropic implementation of `LLMProvider`.

Model: `claude-opus-5` (1,000,000-token context window).

This file is the ONLY place Anthropic SDK types appear. Everything else in the
codebase speaks in terms of `LLMProvider`, `LLMError`, and Pydantic models.

WHY `messages.parse`
--------------------
`client.messages.parse(..., output_format=Model)` constrains the model to our
schema and returns a validated Pydantic instance as `response.parsed_output`.
That removes the most common failure in LLM applications - the model returning
prose, markdown-fenced JSON, or almost-valid JSON that needs regex repair.

Adaptive thinking is on because gap analysis is genuinely analytical work; the
effort level is configurable so tests and smoke runs can turn it down.
"""

import logging
from typing import TypeVar

import anthropic
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


class AnthropicLLMProvider(LLMProvider):
    """Text generation backed by the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-5",
        max_output_tokens: int = 16_000,
        effort: str = "high",
        timeout_seconds: float = 600.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMCredentialsError(
                "ANTHROPIC_API_KEY is not set. ResearchForge cannot analyse a "
                "paper without it. Get a key from https://console.anthropic.com "
                "and put it in .env (never in source code)."
            )
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._effort = effort
        # Analysing a long paper legitimately takes minutes, so the SDK default
        # of 10 minutes is retained rather than shortened.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)

    @property
    def model_name(self) -> str:
        return self._model

    # ---------- shared request plumbing ----------

    def _base_kwargs(self, system: str, prompt: str) -> dict:
        return {
            "model": self._model,
            "max_tokens": self._max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            # Adaptive thinking: the model decides how much reasoning each
            # request needs. budget_tokens is removed on this model family.
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._effort},
        }

    @staticmethod
    def _translate(exc: Exception) -> LLMError:
        """Map an SDK exception onto a project-owned error.

        Ordered most-specific first, so a 401 is never reported as a generic
        API failure.
        """
        if isinstance(exc, anthropic.AuthenticationError):
            return LLMCredentialsError(
                "The Anthropic API rejected the configured key. Check ANTHROPIC_API_KEY."
            )
        if isinstance(exc, anthropic.PermissionDeniedError):
            return LLMCredentialsError(
                "The configured Anthropic key lacks permission for this model."
            )
        if isinstance(exc, anthropic.RateLimitError):
            # The same project-owned type Gemini raises, so the API layer maps
            # a rate limit to 429 whichever provider is configured. Anthropic's
            # SDK does its own bounded retrying and does not hand us a delay,
            # so none is claimed: `retry_after_seconds` stays None rather than
            # carrying a number nobody supplied.
            return LLMRateLimitError(
                "The Anthropic API is rate limiting this key. Please wait and try again."
            )
        if isinstance(exc, anthropic.APITimeoutError):
            return LLMError(
                "The analysis timed out. This paper may be unusually long - "
                "try again, or upload a shorter document."
            )
        if isinstance(exc, anthropic.APIConnectionError):
            return LLMError("Could not reach the Anthropic API. Check network connectivity.")
        if isinstance(exc, anthropic.APIStatusError):
            return LLMError(f"The Anthropic API returned an error: {exc.message}")
        return LLMError(f"Unexpected generation failure: {exc}")

    @staticmethod
    def _check_stop_reason(response) -> None:
        """Reject refusals and truncated output rather than using them."""
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMResponseError(
                "The model declined to analyse this document"
                + (f" (category: {category})" if category else "")
                + ". The upload may contain content it will not process."
            )
        if stop == "max_tokens":
            raise LLMResponseError(
                "The model's response was cut off before it finished. The "
                "paper may be too dense to analyse in one pass."
            )

    # ---------- interface ----------

    def generate_structured(self, *, system: str, prompt: str, output_model: type[T]) -> T:
        try:
            response = self._client.messages.parse(
                **self._base_kwargs(system, prompt),
                output_format=output_model,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        self._check_stop_reason(response)

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise LLMResponseError(
                "The model returned no structured output. The response did not "
                "match the requested schema."
            )
        if not isinstance(parsed, output_model):
            # Defensive: validate rather than trust, so schema drift surfaces
            # here as a clear error instead of a confusing one downstream.
            try:
                raw = parsed if isinstance(parsed, dict) else parsed.model_dump()
                parsed = output_model.model_validate(raw)
            except (ValidationError, AttributeError) as exc:
                raise LLMResponseError(
                    f"The model's output did not match the expected schema: {exc}"
                ) from exc

        logger.info("structured generation ok: %s", output_model.__name__)
        return parsed

    def generate_text(self, *, system: str, prompt: str) -> str:
        try:
            response = self._client.messages.create(**self._base_kwargs(system, prompt))
        except LLMError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        self._check_stop_reason(response)

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            raise LLMResponseError("The model returned an empty response.")
        return text

    def __repr__(self) -> str:
        """Redacted repr - must never expose the API key in logs or tracebacks."""
        return (
            f"AnthropicLLMProvider(model={self._model!r}, "
            f"effort={self._effort!r}, api_key='***redacted***')"
        )
