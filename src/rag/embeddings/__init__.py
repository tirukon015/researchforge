"""Embedding providers.

Import `EmbeddingProvider`, `EmbeddingTask`, and `EmbeddingError` from here.
Never import a concrete provider (e.g. `JinaEmbeddingProvider`) outside the
factory — that would couple the pipeline to one vendor and defeat the
abstraction. See PROJECT_PLAN.md section F, decision 2.
"""

from src.rag.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingTask,
)

__all__ = ["EmbeddingError", "EmbeddingProvider", "EmbeddingTask"]
