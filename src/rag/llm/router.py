"""Primary provider, with one automatic fallback to the other one.

WHAT THIS IS FOR
----------------
ResearchForge runs on two providers, Anthropic Claude and Groq. The owner picks
ONE as primary; the other is automatically the fallback. There is no "auto"
setting to choose - the fallback is not a third option, it is whichever
provider was not chosen.

    owner picks anthropic  ->  primary Claude, fallback Groq
    owner picks groq       ->  primary Groq,   fallback Claude

WHY IT IS ITSELF AN `LLMProvider`
---------------------------------
`analyse_paper` makes several calls (three structured passes, plus one text
pass per chunk on a long paper). Making the router satisfy the same interface
means the analysis service needs no knowledge of routing at all: it keeps
calling `provider.generate_structured(...)` and the switching happens
underneath. Adding fallback therefore changed no business logic.

THE TWO RULES THAT KEEP THIS HONEST
-----------------------------------
**One switch per analysis, not one per call.** The router is built per request
and remembers that it has switched. Without that, a paper needing five calls
could bounce between vendors five times, and the recorded "model used" would be
a fiction - the analysis would have been written by two different models with
no way to say which wrote which part. After a switch it stays switched, so the
remainder of the analysis is produced by one model.

**Fallback only for RETRYABLE failures.** A rate limit or a temporary outage is
the other provider's problem to solve. A bad PDF, a validation failure, a
missing key, or an unknown model is not: retrying those on a second vendor
burns a second quota to produce the same error, and hides the real cause behind
whichever message the fallback happened to give. `is_retryable` is deliberately
a whitelist, so a new error type does not become silently retryable by default.
"""

import logging
import time
from typing import TypeVar

from pydantic import BaseModel

from src.rag.llm.base import (
    LLMCredentialsError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponseError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# The two providers the application supports, and each one's opposite. One
# mapping, so "what is the fallback" has a single answer and cannot drift.
PROVIDERS: tuple[str, str] = ("anthropic", "groq")

OPPOSITE: dict[str, str] = {"anthropic": "groq", "groq": "anthropic"}

# How each provider is named to a person. Used by the interface, so a reader
# sees "Groq Qwen 3.6 27B" rather than a bare key.
DISPLAY_NAMES: dict[str, str] = {
    "anthropic": "Claude",
    "groq": "Groq Qwen 3.6 27B",
}


def display_name(provider: str) -> str:
    """Human label for a provider key, falling back to the key itself."""
    return DISPLAY_NAMES.get(provider, provider)


def is_retryable(exc: Exception) -> bool:
    """Whether `exc` justifies trying the OTHER provider.

    A whitelist, not a blacklist. Anything unrecognised is treated as NOT
    retryable, so a failure mode nobody has thought about yet cannot quietly
    start costing two quotas per analysis.

    Retryable:
      LLMRateLimitError   the provider is fine, we are over an allowance
      LLMError (bare)     a temporary/transport failure: 5xx, timeout, refused
                          connection. The concrete providers raise the bare
                          class for exactly these.

    NOT retryable:
      LLMCredentialsError a missing or rejected key. The other provider's key
                          is a different variable; this one still needs fixing,
                          and masking it would hide a deployment fault.
      LLMResponseError    the model replied with something unusable, or the
                          request was malformed. Usually our prompt or the
                          paper, and the second provider would fail the same way.
      anything else       not ours to interpret.
    """
    if isinstance(exc, LLMRateLimitError):
        return True
    if isinstance(exc, (LLMCredentialsError, LLMResponseError)):
        return False
    return isinstance(exc, LLMError)


class RoutedLLMProvider(LLMProvider):
    """A primary provider that falls back to the other one, at most once.

    Construct one PER ANALYSIS. The switch state is per-instance, and that is
    what limits the analysis to a single change of model.
    """

    def __init__(
        self,
        *,
        primary: LLMProvider,
        primary_key: str,
        fallback: LLMProvider | None,
        fallback_key: str | None,
    ) -> None:
        self._primary = primary
        self._primary_key = primary_key
        self._fallback = fallback
        self._fallback_key = fallback_key

        # Set the moment a call is served by the fallback, and never unset.
        self._switched = False
        self._fallback_reason: str | None = None
        self._started = time.monotonic()

    # ---------- what actually happened ----------

    @property
    def active_key(self) -> str:
        """The provider that is producing output RIGHT NOW."""
        return self._fallback_key if self._switched and self._fallback_key else self._primary_key

    @property
    def model_name(self) -> str:
        """The model that produced the output, for the stored record.

        Reports the ACTIVE model, not the configured one. If Claude was primary
        but Groq wrote the result, this says Groq - otherwise the saved
        analysis would credit a model that never saw the paper.
        """
        active = self._fallback if self._switched and self._fallback else self._primary
        return active.model_name

    @property
    def fallback_used(self) -> bool:
        return self._switched

    @property
    def fallback_reason(self) -> str | None:
        """Why the switch happened, or None. Never contains a key."""
        return self._fallback_reason

    @property
    def elapsed_ms(self) -> int:
        """Wall-clock time since this router was built."""
        return int((time.monotonic() - self._started) * 1000)

    # ---------- the routing itself ----------

    def _call(self, method: str, **kwargs):
        """Run `method` on the active provider, switching once if allowed."""
        if self._switched:
            # Already switched. Stay switched - see the module note on why an
            # analysis must not bounce between vendors.
            return getattr(self._fallback, method)(**kwargs)

        try:
            return getattr(self._primary, method)(**kwargs)
        except Exception as exc:
            if self._fallback is None:
                # Nothing to fall back to. Raise the real error rather than
                # wrapping it: the caller needs the primary's own message.
                raise
            if not is_retryable(exc):
                raise

            self._switched = True
            self._fallback_reason = type(exc).__name__
            logger.warning(
                "provider %s failed with a retryable error (%s); "
                "falling back to %s for the rest of this analysis",
                self._primary_key,
                type(exc).__name__,
                self._fallback_key,
            )
            try:
                return getattr(self._fallback, method)(**kwargs)
            except Exception as fallback_exc:
                # Both are down. Say so plainly rather than reporting only the
                # second failure, which would send someone to debug the wrong
                # vendor. There is deliberately no third attempt.
                raise LLMError(
                    f"Both AI providers failed. "
                    f"{display_name(self._primary_key)} reported: {exc}. "
                    f"{display_name(self._fallback_key or '')} reported: {fallback_exc}"
                ) from fallback_exc

    def generate_structured(self, *, system: str, prompt: str, output_model: type[T]) -> T:
        return self._call(
            "generate_structured", system=system, prompt=prompt, output_model=output_model
        )

    def generate_text(self, *, system: str, prompt: str) -> str:
        return self._call("generate_text", system=system, prompt=prompt)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"RoutedLLMProvider(primary={self._primary_key!r}, "
            f"fallback={self._fallback_key!r}, switched={self._switched})"
        )
