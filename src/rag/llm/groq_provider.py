"""Groq implementation of `LLMProvider`.

Default model: `qwen/qwen3.6-27b`, served on Groq's OpenAI-compatible API.

This file is the ONLY place Groq or OpenAI-wire-format details appear.
Everything else in the codebase speaks in terms of `LLMProvider`, `LLMError`,
and Pydantic models.

WHY httpx AND NOT THE OPENAI SDK
--------------------------------
Groq speaks the OpenAI chat-completions wire format, so the `openai` package
would work. It is not worth the dependency: this file needs one endpoint and
one response shape, httpx is already pinned (the Anthropic and Gemini SDKs both
pull it in, and `src/db/supabase.py` imports it directly), and the deployed
function is already carrying model SDKs. About a hundred lines here removes a
package from the bundle.

HOW STRUCTURED OUTPUT IS OBTAINED
---------------------------------
Anthropic has `messages.parse`, which constrains generation to a schema and
hands back a validated object. Groq has no equivalent for every model, so this
provider does three things instead:

  1. asks for `response_format={"type": "json_object"}`, which constrains the
     model to emit syntactically valid JSON,
  2. puts the exact JSON Schema of the expected model in the system message, so
     the field names and types are stated rather than guessed at,
  3. validates the result with Pydantic and raises `LLMResponseError` if it
     does not fit.

Step 3 is the one that matters. A near-miss is discarded, never repaired: a
"fixed up" analysis is an invented one, and this project's whole claim is that
its output is grounded in the uploaded paper. There is deliberately no regex
salvage and no partial object.
"""

import json
import logging
import re
from typing import Any, TypeVar

import httpx
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

DEFAULT_MODEL = "qwen/qwen3.6-27b"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"

# Appended to the caller's system prompt for a structured call. The schema is
# supplied verbatim rather than described, because a description is a second
# source of truth that can drift away from the Pydantic model.
_JSON_INSTRUCTION = (
    "\n\nYou must reply with a single JSON object and nothing else. No prose, "
    "no explanation, and no markdown code fence. The object must validate "
    "against this JSON Schema:\n\n{schema}\n\n"
    "Every required property must be present. Where the source text does not "
    "support a field, use the schema's own way of saying so (an empty list, or "
    "the insufficient-evidence flag) rather than inventing content."
)


def _strip_code_fence(text: str) -> str:
    """Remove a ```json fence if the model added one anyway.

    This is presentation, not content: the JSON inside is untouched, and if
    what is inside is not valid the call still fails. It exists because a
    fence is the single most common way an otherwise perfect response becomes
    unparseable, and refusing it would waste a correct answer.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    fence = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", stripped, re.DOTALL)
    return fence.group(1).strip() if fence else stripped


class GroqLLMProvider(LLMProvider):
    """Text generation backed by Groq's OpenAI-compatible chat completions."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = 16_000,
        effort: str = "high",
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 600.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMCredentialsError(
                "GROQ_API_KEY is not set. ResearchForge cannot analyse a paper "
                "with Groq without it. Get a key from https://console.groq.com "
                "and put it in .env (never in source code)."
            )
        self._api_key = api_key.strip()
        self._model = model
        self._max_output_tokens = max_output_tokens
        # Temperature, not a reasoning-effort parameter: Groq's chat API has no
        # equivalent of Anthropic's thinking budget. Analytical work wants
        # determinism, so "high" effort means a LOWER temperature here. The
        # argument is accepted so the two providers stay swappable behind one
        # configuration value.
        self._temperature = 0.2 if effort == "high" else 0.5
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    # ---------- plumbing ----------

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        """Seconds the provider asked us to wait, when it said anything.

        Returns None rather than a default when absent. A guess here would be
        counted down in the interface as though it were the provider's own
        instruction, which is a fabricated fact on a screen.
        """
        raw = response.headers.get("retry-after")
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
        # Groq also reports remaining allowance as e.g. "2m59.56s".
        reset = response.headers.get("x-ratelimit-reset-requests") or response.headers.get(
            "x-ratelimit-reset-tokens"
        )
        if reset:
            match = re.match(r"^(?:(\d+(?:\.\d+)?)m)?(\d+(?:\.\d+)?)s$", reset.strip())
            if match:
                minutes = float(match.group(1) or 0)
                return minutes * 60 + float(match.group(2))
        return None

    def _translate(self, exc: Exception) -> LLMError:
        if isinstance(exc, httpx.TimeoutException):
            return LLMError(
                "Groq did not respond in time. Very long papers can exceed the "
                "limit; please try again."
            )
        if isinstance(exc, httpx.RequestError):
            return LLMError("Could not reach Groq. Please try again.")
        return LLMError("Groq could not complete that request.")

    def _check(self, response: httpx.Response) -> None:
        """Raise the right typed error for a non-2xx reply. Never echoes the key."""
        if response.is_success:
            return

        detail = ""
        code = ""
        try:
            body = response.json()
            err = body.get("error") or {}
            detail = str(err.get("message") or "")
            code = str(err.get("code") or "")
        except Exception:  # noqa: BLE001 - a non-JSON error body is still an error
            pass

        if response.status_code == 429:
            wait = self._retry_after(response)
            # `quota_exhausted` is set only on POSITIVE evidence of a long
            # allowance, matching the contract in base.py: a delay longer than
            # a couple of minutes is not something to sit out, and daily quota
            # messages say so explicitly.
            exhausted = bool(
                (wait is not None and wait > 120)
                or "per day" in detail.lower()
                or "daily" in detail.lower()
            )
            raise LLMRateLimitError(
                "Groq is rate limiting requests"
                + (f"; it asked us to wait {wait:.0f} seconds." if wait else " right now.")
                + (
                    " The daily allowance appears to be spent."
                    if exhausted
                    else " Please try again shortly."
                ),
                retry_after_seconds=wait,
                quota_exhausted=exhausted,
            )
        if response.status_code in (401, 403):
            raise LLMCredentialsError(
                "Groq rejected the API key. Check GROQ_API_KEY on the server."
            )
        if response.status_code == 404 or code == "model_not_found":
            # Permanent and NOT retryable: falling back is right, but retrying
            # this provider is not, and the message must name the variable.
            raise LLMError(
                f"Groq does not offer the model {self._model!r}. Set GROQ_MODEL "
                "to a model the account can use."
            )
        if response.status_code == 400:
            raise LLMResponseError(detail or "Groq rejected the request as malformed.")
        if response.status_code >= 500:
            raise LLMError("Groq is temporarily unavailable. Please try again.")

        logger.warning("groq request failed: %s %s", response.status_code, code)
        raise LLMError(detail or "Groq refused the request.")

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except Exception as exc:
            raise self._translate(exc) from exc
        self._check(response)
        try:
            return response.json()
        except ValueError as exc:
            raise LLMResponseError("Groq returned a response that was not valid JSON.") from exc

    @staticmethod
    def _content(body: dict[str, Any]) -> str:
        """Pull the assistant message out, or fail loudly."""
        choices = body.get("choices") or []
        if not choices:
            raise LLMResponseError("Groq returned no completion.")
        choice = choices[0]
        # A response cut off at the token ceiling is truncated, not merely
        # short. Returning it would silently drop the end of an analysis.
        if choice.get("finish_reason") == "length":
            raise LLMResponseError(
                "Groq's reply was cut off at the output limit, so the result is "
                "incomplete. Try a shorter paper, or raise LLM_MAX_OUTPUT_TOKENS."
            )
        content = (choice.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("Groq returned an empty completion.")
        return content

    def _messages(self, system: str, prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

    # ---------- the interface ----------

    def generate_structured(self, *, system: str, prompt: str, output_model: type[T]) -> T:
        schema = json.dumps(output_model.model_json_schema(), indent=2)
        body = self._post(
            {
                "model": self._model,
                "messages": self._messages(
                    system + _JSON_INSTRUCTION.format(schema=schema), prompt
                ),
                "max_tokens": self._max_output_tokens,
                "temperature": self._temperature,
                "response_format": {"type": "json_object"},
            }
        )
        text = _strip_code_fence(self._content(body))

        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise LLMResponseError(
                "Groq's reply was not valid JSON, so the analysis could not be read."
            ) from exc

        try:
            return output_model.model_validate(parsed)
        except ValidationError as exc:
            # Deliberately NOT repaired. A partially-valid analysis that we
            # patched up is an invented one, and the product's claim is that
            # every section is grounded in the paper.
            logger.warning("groq output failed schema validation: %s", exc.error_count())
            raise LLMResponseError(
                "Groq returned an analysis that did not match the expected "
                "structure, so it was discarded rather than partially used."
            ) from exc

    def generate_text(self, *, system: str, prompt: str) -> str:
        body = self._post(
            {
                "model": self._model,
                "messages": self._messages(system, prompt),
                "max_tokens": self._max_output_tokens,
                "temperature": self._temperature,
            }
        )
        return self._content(body).strip()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"GroqLLMProvider(model={self._model!r}, base_url={self._base_url!r})"
