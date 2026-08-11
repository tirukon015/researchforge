"""Jina AI implementation of `EmbeddingProvider`.

Model: `jina-embeddings-v3` — 1024 dimensions, 8,192-token input, 89 languages.
Paper: https://arxiv.org/abs/2409.10173

ASYMMETRIC RETRIEVAL — the reason this model was chosen
-------------------------------------------------------
`jina-embeddings-v3` ships task-specific LoRA adapters. Documents are embedded
with `retrieval.passage` and questions with `retrieval.query`, so each is
encoded by an adapter trained for its role. Most RAG implementations embed both
identically and discard this advantage.

This file is the **only** place those Jina task strings appear. Everything else
in the codebase speaks in terms of `EmbeddingTask.DOCUMENT` / `.QUERY`.

⚠️ NETWORK CALLS ARE NOT IMPLEMENTED YET (Milestone 4).
Request construction below is complete and unit-tested offline. The HTTP send
is deliberately deferred until the milestone that can verify it against the
real API — this project does not ship untested network code.
"""

from src.rag.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingTask,
)

# Jina's own vocabulary for the abstract tasks in base.py.
# Confining these strings here is what keeps the rest of the system portable.
_JINA_TASK_BY_EMBEDDING_TASK: dict[EmbeddingTask, str] = {
    EmbeddingTask.DOCUMENT: "retrieval.passage",
    EmbeddingTask.QUERY: "retrieval.query",
}

API_URL = "https://api.jina.ai/v1/embeddings"

# Chunks per HTTP request. Batching is a hard requirement: the free
# allocation is finite, and one request per chunk would waste it.
DEFAULT_BATCH_SIZE = 64


class JinaEmbeddingProvider(EmbeddingProvider):
    """Embeddings backed by the Jina AI API."""

    def __init__(
        self,
        api_key: str,
        model: str = "jina-embeddings-v3",
        dimensions: int = 1024,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if not api_key:
            raise EmbeddingError(
                "JINA_API_KEY is not set. Get a free key at "
                "https://jina.ai/embeddings/ and put it in .env "
                "(never in source code)."
            )
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size

    # ---------- interface ----------

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Jina network calls arrive in Milestone 4 (Chunking & Embedding)."
        )

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Jina network calls arrive in Milestone 4 (Chunking & Embedding)."
        )

    # ---------- request construction (unit-tested offline) ----------

    def build_payload(self, texts: list[str], task: EmbeddingTask) -> dict:
        """Build the JSON body for an embeddings request.

        Separated from the HTTP call so the request shape — especially the
        task mode, which is the whole point of choosing this model — can be
        verified in tests without spending a single token.
        """
        if not texts:
            raise EmbeddingError("Cannot embed an empty list of texts.")

        return {
            "model": self._model,
            "task": _JINA_TASK_BY_EMBEDDING_TASK[task],
            "dimensions": self._dimensions,
            # Ask the API to return unit-length vectors so cosine similarity
            # behaves correctly in pgvector without post-processing.
            "normalized": True,
            "embedding_type": "float",
            "input": list(texts),
        }

    def build_headers(self) -> dict[str, str]:
        """Build request headers.

        The API key is read from configuration and never logged. Anything that
        prints headers must redact `Authorization`.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def iter_batches(self, texts: list[str]) -> list[list[str]]:
        """Split texts into batches to limit request count and size."""
        return [texts[i : i + self._batch_size] for i in range(0, len(texts), self._batch_size)]

    def __repr__(self) -> str:
        """Redacted repr — must never expose the API key in logs or tracebacks."""
        return (
            f"JinaEmbeddingProvider(model={self._model!r}, "
            f"dimensions={self._dimensions}, api_key='***redacted***')"
        )
