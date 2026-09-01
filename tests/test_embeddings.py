"""Tests for the embedding abstraction.

⚠️ NO NETWORK CALLS. Every test here runs offline and spends zero tokens.
Tests must be free, fast, and deterministic, see CLAUDE.md section 9.

Two things are verified:
  1. The `EmbeddingProvider` interface is genuinely provider-independent.
  2. The Jina provider builds the *correct request*, especially the
     asymmetric task modes, the reason this model was chosen.
"""

import pytest

from src.config import Settings
from src.rag.embeddings import EmbeddingError, EmbeddingProvider, EmbeddingTask
from src.rag.embeddings.jina import JinaEmbeddingProvider

FAKE_KEY = "test-key-not-a-real-credential"


class FakeProvider(EmbeddingProvider):
    """A stand-in provider used to prove the interface is vendor-neutral.

    If this class can satisfy the contract without importing anything
    vendor-specific, the abstraction is doing its job.
    """

    def __init__(self, dimensions: int = 1024) -> None:
        self._dimensions = dimensions
        self.documents_seen: list[str] = []
        self.queries_seen: list[str] = []

    @property
    def model_name(self) -> str:
        return "fake-model-v1"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents_seen.extend(texts)
        return [[0.1] * self._dimensions for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries_seen.append(text)
        return [0.2] * self._dimensions


class TestEmbeddingProviderContract:
    """The interface must be satisfiable without any vendor coupling."""

    def test_fake_provider_satisfies_the_interface(self) -> None:
        assert isinstance(FakeProvider(), EmbeddingProvider)

    def test_embed_documents_returns_one_vector_per_input(self) -> None:
        provider = FakeProvider()
        vectors = provider.embed_documents(["chunk one", "chunk two", "chunk three"])
        assert len(vectors) == 3

    def test_every_vector_has_the_declared_dimension(self) -> None:
        provider = FakeProvider(dimensions=1024)
        for vector in provider.embed_documents(["a", "b"]):
            assert len(vector) == 1024

    def test_embed_query_returns_a_single_vector(self) -> None:
        provider = FakeProvider(dimensions=1024)
        assert len(provider.embed_query("What are the limitations?")) == 1024

    def test_interface_cannot_be_instantiated_directly(self) -> None:
        """An abstract contract must not be usable on its own."""
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]


class TestDimensionValidation:
    """A wrong-length vector must fail loudly, not reach the database."""

    def test_correct_dimension_passes(self) -> None:
        provider = FakeProvider(dimensions=1024)
        provider.validate_dimensions([0.0] * 1024)  # must not raise

    def test_wrong_dimension_raises(self) -> None:
        provider = FakeProvider(dimensions=1024)
        with pytest.raises(EmbeddingError):
            provider.validate_dimensions([0.0] * 768)

    def test_error_message_is_actionable(self) -> None:
        provider = FakeProvider(dimensions=1024)
        with pytest.raises(EmbeddingError) as exc:
            provider.validate_dimensions([0.0] * 512)
        message = str(exc.value)
        assert "512" in message and "1024" in message


class TestJinaAsymmetricRetrieval:
    """The task modes are the reason this model was chosen, verify them."""

    def provider(self) -> JinaEmbeddingProvider:
        return JinaEmbeddingProvider(api_key=FAKE_KEY)

    def test_documents_use_retrieval_passage(self) -> None:
        payload = self.provider().build_payload(["a chunk"], EmbeddingTask.DOCUMENT)
        assert payload["task"] == "retrieval.passage"

    def test_queries_use_retrieval_query(self) -> None:
        payload = self.provider().build_payload(["a question"], EmbeddingTask.QUERY)
        assert payload["task"] == "retrieval.query"

    def test_document_and_query_modes_differ(self) -> None:
        """If these ever match, asymmetric retrieval has been broken."""
        p = self.provider()
        doc = p.build_payload(["x"], EmbeddingTask.DOCUMENT)["task"]
        qry = p.build_payload(["x"], EmbeddingTask.QUERY)["task"]
        assert doc != qry


class TestJinaRequestConstruction:
    def provider(self) -> JinaEmbeddingProvider:
        return JinaEmbeddingProvider(api_key=FAKE_KEY)

    def test_payload_requests_1024_dimensions(self) -> None:
        payload = self.provider().build_payload(["x"], EmbeddingTask.DOCUMENT)
        assert payload["dimensions"] == 1024

    def test_payload_names_the_model(self) -> None:
        payload = self.provider().build_payload(["x"], EmbeddingTask.DOCUMENT)
        assert payload["model"] == "jina-embeddings-v3"

    def test_payload_requests_normalised_vectors(self) -> None:
        """Unit-length vectors make pgvector cosine distance behave correctly."""
        payload = self.provider().build_payload(["x"], EmbeddingTask.DOCUMENT)
        assert payload["normalized"] is True

    def test_payload_preserves_input_order(self) -> None:
        texts = ["first", "second", "third"]
        payload = self.provider().build_payload(texts, EmbeddingTask.DOCUMENT)
        assert payload["input"] == texts

    def test_empty_input_raises(self) -> None:
        with pytest.raises(EmbeddingError):
            self.provider().build_payload([], EmbeddingTask.DOCUMENT)

    def test_missing_api_key_raises_with_guidance(self) -> None:
        with pytest.raises(EmbeddingError) as exc:
            JinaEmbeddingProvider(api_key="")
        assert "JINA_API_KEY" in str(exc.value)


class TestJinaBatching:
    """Batching is mandatory, the free token allocation is finite."""

    def test_texts_are_split_into_batches(self) -> None:
        provider = JinaEmbeddingProvider(api_key=FAKE_KEY, batch_size=10)
        batches = provider.iter_batches([f"chunk {i}" for i in range(25)])
        assert [len(b) for b in batches] == [10, 10, 5]

    def test_batching_loses_no_texts(self) -> None:
        provider = JinaEmbeddingProvider(api_key=FAKE_KEY, batch_size=7)
        texts = [f"chunk {i}" for i in range(30)]
        flattened = [t for batch in provider.iter_batches(texts) for t in batch]
        assert flattened == texts


class TestApiKeyIsNeverLeaked:
    """A key in a log or traceback is a leaked key."""

    def test_repr_redacts_the_key(self) -> None:
        provider = JinaEmbeddingProvider(api_key="super-secret-value-12345")
        assert "super-secret-value-12345" not in repr(provider)
        assert "redacted" in repr(provider)

    def test_headers_carry_the_key_but_repr_does_not(self) -> None:
        """The key must reach the API, yet never appear in a printed object."""
        provider = JinaEmbeddingProvider(api_key="super-secret-value-12345")
        assert provider.build_headers()["Authorization"].endswith("12345")
        assert "12345" not in repr(provider)


class TestEmbeddingSettings:
    """Configuration must match the locked decision and the database column."""

    def settings(self) -> Settings:
        return Settings(_env_file=None)  # type: ignore[call-arg]

    def test_provider_defaults_to_jina(self) -> None:
        assert self.settings().embedding_provider == "jina"

    def test_model_defaults_to_jina_embeddings_v3(self) -> None:
        assert self.settings().embedding_model == "jina-embeddings-v3"

    def test_dimensions_default_to_1024(self) -> None:
        """Must equal the vector(1024) column, or every insert fails."""
        assert self.settings().embedding_dimensions == 1024

    def test_dimensions_are_under_the_pgvector_index_limit(self) -> None:
        """pgvector can only build HNSW/IVFFlat indexes up to 2000 dims."""
        assert self.settings().embedding_dimensions <= 2000

    def test_no_api_key_is_hardcoded(self) -> None:
        """The default must be empty, a key belongs only in .env."""
        assert self.settings().jina_api_key == ""
        assert self.settings().has_embedding_credentials is False


class TestMigrationMatchesConfiguration:
    """The single most expensive mistake would be these drifting apart."""

    def migration_sql(self) -> str:
        from pathlib import Path

        from src.config import PROJECT_ROOT

        path: Path = PROJECT_ROOT / "src" / "db" / "migrations" / "001_initial_schema.sql"
        return path.read_text(encoding="utf-8")

    def test_migration_column_matches_configured_dimensions(self) -> None:
        dims = Settings(_env_file=None).embedding_dimensions  # type: ignore[call-arg]
        assert f"vector({dims})" in self.migration_sql()

    def test_migration_has_no_stale_dimension(self) -> None:
        sql = self.migration_sql()
        assert "vector(1536)" not in sql
        assert "vector(768)" not in sql
        assert "vector(3072)" not in sql

    def test_migration_contains_no_destructive_sql(self) -> None:
        """Statement-initial DROP / TRUNCATE / DELETE are forbidden."""
        import re

        executable = [
            line for line in self.migration_sql().splitlines() if not line.strip().startswith("--")
        ]
        for line in executable:
            assert not re.match(r"^\s*(DROP|TRUNCATE|DELETE)\b", line, re.IGNORECASE), (
                f"destructive statement found: {line!r}"
            )
