"""Provider-independent embedding interface.

WHY THIS FILE EXISTS
--------------------
An *embedding* turns text into a list of numbers that represents its meaning.
Text with similar meaning produces similar numbers, which is what lets us
search a paper library by meaning instead of by keyword.

The **dimension count is permanent** — it is baked into the database column
type (`vector(1024)`), and changing it means re-embedding every paper. That
makes the choice of provider expensive to reverse *unless* the rest of the
system is written against an interface rather than against one vendor.

That is what this file is: the contract every provider must satisfy.

**Nothing in this file may be vendor-specific.** No Jina types, no Jina task
strings, no Jina URLs. Ingestion and retrieval code imports only from here, so
swapping providers becomes a configuration change plus a re-index — never a
rewrite. Vendor details belong in the concrete implementation (e.g. `jina.py`).

WHY THERE ARE TWO EMBED METHODS
-------------------------------
`embed_documents()` and `embed_query()` are deliberately separate, because
questions and passages are different kinds of text:

    query:   "What are the limitations of attention?"   (short, interrogative)
    passage: "A known drawback of self-attention is..."  (long, declarative)

Good retrieval models encode each with a mode tuned for its role — called
*asymmetric retrieval*. A provider that has no such distinction can simply
implement both methods the same way; the interface stays valid either way.
"""

from abc import ABC, abstractmethod
from enum import StrEnum


class EmbeddingTask(StrEnum):
    """What a piece of text is being embedded *for*.

    Deliberately abstract. `DOCUMENT` means "text being stored and searched
    over"; `QUERY` means "text being searched with". Each provider maps these
    onto its own vocabulary (or ignores them if it has no such concept).
    """

    DOCUMENT = "document"
    QUERY = "query"


class EmbeddingError(RuntimeError):
    """Raised when a provider cannot produce embeddings.

    Wrapping vendor errors in one project-owned exception means calling code
    never has to import a vendor's error classes — which would defeat the
    whole point of this abstraction.
    """


class EmbeddingProvider(ABC):
    """The contract every embedding provider must satisfy."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the model, stored in `chunks.embedding_model`.

        Recorded per chunk so a future migration can tell exactly which rows
        were produced by which model. Vectors from two different models are
        **not** comparable — mixing them returns meaningless results with no
        error, so this column is what makes a provider switch safe.
        """

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Length of each returned vector.

        Must match the `vector(N)` column in the database exactly, or inserts
        fail. Stored per chunk in `chunks.embedding_dimensions`.
        """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed chunks of papers for storage and search.

        Called at ingestion time. Implementations should send texts in
        batches rather than one request per chunk.

        Returns one vector per input, in the same order. Raises
        `EmbeddingError` on failure.
        """

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a user's question for searching against stored chunks.

        Returns a single vector of length `self.dimensions`. Raises
        `EmbeddingError` on failure.
        """

    def validate_dimensions(self, vector: list[float]) -> None:
        """Fail loudly if a vector is the wrong length.

        A wrong-length vector is rejected by Postgres anyway, but catching it
        here produces a far clearer message than a database type error — and
        catches a misconfigured provider before it writes anything.
        """
        if len(vector) != self.dimensions:
            raise EmbeddingError(
                f"{self.model_name} returned a {len(vector)}-dimension vector, "
                f"but {self.dimensions} was expected. The database column, the "
                f"EMBEDDING_DIMENSIONS setting, and the model must all agree."
            )
