"""Provider-independent text-generation interface.

WHY THIS FILE EXISTS
--------------------
Decision D5 (which LLM vendor) is still formally OPEN, and root CLAUDE.md
section 9 forbids committing to one without the owner's approval. This module is
how the project stays honest about that: the analysis service depends on this
interface, never on a vendor SDK. Adding a second provider is a new file plus an
`LLM_PROVIDER` change - never a rewrite.

It mirrors `src/rag/embeddings/base.py`, which solves the same problem for
embeddings, so the codebase has one pattern rather than two.

**Nothing in this file may be vendor-specific.** No Anthropic types, no model
IDs, no SDK exceptions. Those belong in the concrete implementation.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Base class for every generation failure.

    Wrapping vendor errors in project-owned exceptions means the API layer
    never imports a vendor's error classes - which would defeat the point of
    this abstraction.
    """


class LLMCredentialsError(LLMError):
    """No usable API key is configured.

    Separate from the others because it is the one failure that is a
    deployment/configuration problem rather than a runtime fault, and the API
    layer maps it to a different status code and a different message.
    """


class LLMResponseError(LLMError):
    """The model replied, but not with something usable.

    Covers a refusal, a truncated response, and output that failed schema
    validation. All three mean "we have no trustworthy result", and the caller
    must not fall back to inventing one.
    """


class LLMProvider(ABC):
    """The contract every generation provider must satisfy."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the model, recorded alongside every analysis.

        Stored so an output can always be traced to the model that produced
        it - the same provenance argument as `chunks.embedding_model`.
        """

    @abstractmethod
    def generate_structured(self, *, system: str, prompt: str, output_model: type[T]) -> T:
        """Generate a response validated against `output_model`.

        Returns a validated instance of `output_model`. Raises `LLMError` (or a
        subclass) on any failure - it must never return a partially-filled or
        invented object.
        """

    @abstractmethod
    def generate_text(self, *, system: str, prompt: str) -> str:
        """Generate free text. Used for the map step over long papers."""
