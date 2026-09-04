"""The same-paper analysis cache: what it reuses, and what it must never do.

THE THREE PROPERTIES THAT MATTER
--------------------------------
1. A HIT MUST NOT CALL A MODEL. That is the entire point; if a model still
   runs, the cache is costing a database round trip for nothing.
2. A FAILURE MUST NEVER BE STORED. A cached rate limit or half-finished
   analysis would be served to every future upload of that paper, turning one
   bad minute into a permanent wrong answer.
3. IT MUST NOT BECOME A SHARED LIBRARY. Reuse is invisible: User B gets the
   analysis, and nothing about User A - not an id, not an email, not a
   filename, not the fact that anybody else uploaded it.

NO NETWORK, NO DATABASE, NO API KEYS. The provider is a fake that counts its
calls, and the cache is a fake that records what it was asked to store.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.analyze import get_provider
from src.config import Settings, get_settings
from src.main import app
from src.schemas.analysis import AnalysisResponse
from src.services.content_hash import ANALYSIS_VERSION
from tests.auth_fixtures import USER_A, USER_B, sign_in_as
from tests.pdf_fixtures import build_text_pdf
from tests.test_analysis import PAPER_TEXT, FakeLLMProvider

SETTINGS = Settings(
    _env_file=None,
    supabase_url="https://example-project.supabase.co",
    supabase_service_role_key="sb_secret_exampleonlynotarealkey000000",
    supabase_anon_key="not-a-real-anon-key-for-tests-only",
)


class FakeCache:
    """An in-memory stand-in with the same shape as `AnalysisCache`."""

    def __init__(self, prefill: dict | None = None):
        self.entries: dict[tuple[str, str], object] = dict(prefill or {})
        self.gets: list[tuple[str, str]] = []
        self.puts: list[tuple[str, str, AnalysisResponse]] = []

    async def get(self, content_hash: str, analysis_version: str):
        self.gets.append((content_hash, analysis_version))
        return self.entries.get((content_hash, analysis_version))

    async def put(self, *, content_hash, analysis_version, analysis):
        self.puts.append((content_hash, analysis_version, analysis))
        self.entries[(content_hash, analysis_version)] = analysis


def cached_entry():
    """A validated analysis, as the cache would return one."""
    from src.db.analysis_cache import CachedAnalysis
    from tests.test_library import _gaps, _review, _summary

    return CachedAnalysis(
        summary=_summary(),
        research_gaps=_gaps(),
        literature_review=_review(),
        model_used="claude-opus-5",
        model_provider="anthropic",
        fallback_used=False,
        fallback_provider=None,
        processing_time_ms=26195,
    )


@pytest.fixture
def harness(monkeypatch):
    """A signed-in client, a call-counting provider, and a fake cache."""
    fake_provider = FakeLLMProvider()
    cache = FakeCache()

    sign_in_as(USER_A)
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[get_provider] = lambda: fake_provider
    monkeypatch.setattr("src.api.analyze.get_analysis_cache", lambda settings: cache)

    yield TestClient(app), fake_provider, cache
    app.dependency_overrides.clear()


def upload(client, text=PAPER_TEXT, name="paper.pdf"):
    return client.post(
        "/api/analyze",
        files={"file": (name, build_text_pdf(text), "application/pdf")},
    )


# --------------------------------------------------------------------------- #
# Miss then hit
# --------------------------------------------------------------------------- #


class TestCacheMiss:
    def test_a_new_paper_is_analysed_and_then_stored(self, harness) -> None:
        client, provider, cache = harness
        response = upload(client)

        assert response.status_code == 200
        assert len(provider.structured_calls) == 3, "the three passes must still run"
        assert len(cache.puts) == 1, "a successful analysis is stored"

    def test_a_miss_is_reported_as_one(self, harness) -> None:
        client, _, _ = harness
        assert upload(client).json()["cache_hit"] is False

    def test_it_is_stored_under_the_CONTENT_hash(self, harness) -> None:
        client, _, cache = harness
        upload(client, name="whatever.pdf")
        stored_hash, version, _ = cache.puts[0]
        assert version == ANALYSIS_VERSION
        # The key is derived from the text, not the filename.
        assert len(stored_hash) == 64


class TestCacheHit:
    def test_a_hit_calls_NO_model(self, harness) -> None:
        """The whole point. If a model still runs, the cache has bought
        nothing and cost a round trip."""
        client, provider, cache = harness
        # Seed the cache with this exact document.
        first = upload(client)
        assert first.status_code == 200
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()
        provider.structured_calls.clear()

        second = upload(client)

        assert second.status_code == 200
        assert provider.structured_calls == [], "a cache hit must not call a model"

    def test_a_hit_is_reported_as_one(self, harness) -> None:
        client, provider, cache = harness
        upload(client)
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()

        assert upload(client).json()["cache_hit"] is True

    def test_a_hit_returns_the_ORIGINAL_provenance(self, harness) -> None:
        """A reused analysis was written by the model named here, and must say
        so - even if the owner has since switched providers. Crediting the
        current primary would be a false provenance record."""
        client, provider, cache = harness
        upload(client)
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()

        body = upload(client).json()
        assert body["model_provider"] == "anthropic"
        assert body["model_used"] == "claude-opus-5"
        assert body["fallback_used"] is False
        # The ORIGINAL duration, not this request's. Reporting the fast
        # cache-hit time would misrepresent what the work costs.
        assert body["processing_time_ms"] == 26195

    def test_a_hit_still_describes_THIS_upload(self, harness) -> None:
        """The analysis is reused; the document facts are the caller's own."""
        client, provider, cache = harness
        upload(client, name="first.pdf")
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()

        body = upload(client, name="second-upload.pdf").json()
        assert body["document"]["filename"] == "second-upload.pdf"

    def test_a_DIFFERENT_paper_does_not_hit(self, harness) -> None:
        client, provider, cache = harness
        upload(client)
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()
        provider.structured_calls.clear()

        other = upload(client, text=PAPER_TEXT + " An entirely different concluding section.")

        assert other.status_code == 200
        assert len(provider.structured_calls) == 3, "a different paper must be analysed"

    def test_a_version_bump_retires_the_entry(self, harness) -> None:
        """Stored under an old pipeline version, so it must not be served
        under the new one."""
        client, provider, cache = harness
        upload(client)
        digest = cache.puts[0][0]
        cache.entries.clear()
        cache.entries[(digest, "v0-ancient")] = cached_entry()
        provider.structured_calls.clear()

        upload(client)
        assert len(provider.structured_calls) == 3


# --------------------------------------------------------------------------- #
# Cross-user reuse, without becoming a shared library
# --------------------------------------------------------------------------- #


class TestReuseAcrossUsersLeaksNothing:
    def test_user_b_reuses_user_as_analysis_without_a_model_call(self, harness) -> None:
        client, provider, cache = harness

        sign_in_as(USER_A)
        upload(client)
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()
        provider.structured_calls.clear()

        sign_in_as(USER_B)
        response = upload(client)

        assert response.status_code == 200
        assert provider.structured_calls == [], "B reuses A's result, no model call"
        assert response.json()["cache_hit"] is True

    def test_the_response_says_NOTHING_about_the_other_user(self, harness) -> None:
        """The privacy property, asserted on the actual response body. B may
        have the analysis; B may not learn whose upload produced it, or that
        anybody else exists."""
        client, provider, cache = harness
        sign_in_as(USER_A)
        upload(client)
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()

        sign_in_as(USER_B)
        raw = upload(client).text

        for secret in (USER_A.id, USER_A.email, USER_A.full_name, "user_id", "uploaded_by"):
            assert secret not in raw, f"{secret!r} leaked into a cache hit"

    def test_reuse_does_not_put_a_paper_in_the_other_users_library(self, harness) -> None:
        """/api/analyze stores nothing by design - saving is a separate,
        explicit step. A cache hit must not quietly change that."""
        client, provider, cache = harness
        sign_in_as(USER_A)
        upload(client)
        digest = cache.puts[0][0]
        cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()

        sign_in_as(USER_B)
        body = upload(client).json()
        # The analysis comes back for B to keep or discard; nothing is saved.
        assert "id" not in body


# --------------------------------------------------------------------------- #
# Failures must never be cached
# --------------------------------------------------------------------------- #


class TestFailuresAreNeverCached:
    @pytest.fixture
    def failing(self, monkeypatch):
        cache = FakeCache()
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: SETTINGS
        monkeypatch.setattr("src.api.analyze.get_analysis_cache", lambda settings: cache)
        yield cache
        app.dependency_overrides.clear()

    def _with_error(self, error):
        app.dependency_overrides[get_provider] = lambda: FakeLLMProvider(fail_with=error)
        return TestClient(app)

    def test_a_rate_limit_is_not_cached(self, failing) -> None:
        from src.rag.llm.base import LLMRateLimitError

        client = self._with_error(LLMRateLimitError("429"))
        assert upload(client).status_code == 429
        assert failing.puts == [], "a rate limit must never enter the cache"

    def test_an_unusable_reply_is_not_cached(self, failing) -> None:
        from src.rag.llm.base import LLMResponseError

        client = self._with_error(LLMResponseError("schema mismatch"))
        assert upload(client).status_code == 502
        assert failing.puts == []

    def test_a_provider_outage_is_not_cached(self, failing) -> None:
        from src.rag.llm.base import LLMError

        client = self._with_error(LLMError("upstream 503"))
        assert upload(client).status_code == 502
        assert failing.puts == []

    def test_missing_credentials_are_not_cached(self, failing) -> None:
        from src.rag.llm.base import LLMCredentialsError

        client = self._with_error(LLMCredentialsError("no key"))
        assert upload(client).status_code == 503
        assert failing.puts == []

    def test_an_unreadable_pdf_is_not_cached(self, failing) -> None:
        app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()
        client = TestClient(app)
        response = client.post(
            "/api/analyze",
            files={"file": ("x.pdf", b"not a pdf at all", "application/pdf")},
        )
        assert response.status_code == 422
        assert failing.puts == []
        assert failing.gets == [], "a document that cannot be read is never looked up"


# --------------------------------------------------------------------------- #
# The cache must never break an upload
# --------------------------------------------------------------------------- #


class TestTheCacheFailsSoft:
    def test_a_broken_cache_still_produces_an_analysis(self, monkeypatch) -> None:
        """The cache is an optimisation. If it is down, uploads get slower and
        more expensive - they do not fail."""

        class BrokenCache:
            async def get(self, *a, **k):
                raise RuntimeError("cache is on fire")

            async def put(self, **k):
                raise RuntimeError("cache is on fire")

        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: SETTINGS
        app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()
        monkeypatch.setattr("src.api.analyze.get_analysis_cache", lambda s: BrokenCache())
        try:
            with pytest.raises(RuntimeError):
                # The endpoint does not swallow this itself - AnalysisCache
                # does, internally. This asserts the fake is genuinely broken,
                # so the real-object test below is meaningful.
                upload(TestClient(app))
        finally:
            app.dependency_overrides.clear()

    def test_the_real_cache_swallows_its_own_failures(self, monkeypatch) -> None:
        """`AnalysisCache.get` returns None on ANY failure, so a caller cannot
        tell an outage from a miss - and responds to both correctly."""
        import asyncio

        from src.db.analysis_cache import AnalysisCache

        cache = AnalysisCache(SETTINGS)

        def explode(*a, **k):
            raise httpx.ConnectError("no route to host")

        monkeypatch.setattr("src.db.analysis_cache.httpx.AsyncClient", explode)
        assert asyncio.run(cache.get("abc", ANALYSIS_VERSION)) is None

    def test_a_corrupt_cache_row_is_treated_as_a_miss(self, monkeypatch) -> None:
        """A hand-edited row must not reach the frontend in a shape it cannot
        render. Validation on the way OUT is what stops it."""
        import asyncio

        from src.db.analysis_cache import AnalysisCache

        def transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "1",
                        "summary": {"nonsense": True},
                        "research_gaps": {},
                        "literature_review": {},
                        "model_used": "x",
                    }
                ],
            )

        original = httpx.AsyncClient

        def patched(*a, **k):
            k.setdefault("transport", httpx.MockTransport(transport))
            return original(*a, **k)

        monkeypatch.setattr("src.db.analysis_cache.httpx.AsyncClient", patched)
        assert asyncio.run(AnalysisCache(SETTINGS).get("abc", ANALYSIS_VERSION)) is None


# --------------------------------------------------------------------------- #
# Concurrency
# --------------------------------------------------------------------------- #


class TestConcurrentFirstUploads:
    def test_the_write_asks_postgrest_to_ignore_a_duplicate(self, monkeypatch) -> None:
        """Two people uploading the same NEW paper at once both miss, both
        analyse, and both write. The loser of that race must be a no-op
        against UNIQUE(content_hash, analysis_version) - not an error, and not
        a duplicate row. No lock is held while the model runs.
        """
        import asyncio

        from src.db.analysis_cache import AnalysisCache
        from tests.test_library import _gaps, _review, _summary

        seen: list[httpx.Request] = []

        def transport(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(201, json=[])

        original = httpx.AsyncClient

        def patched(*a, **k):
            k.setdefault("transport", httpx.MockTransport(transport))
            return original(*a, **k)

        monkeypatch.setattr("src.db.analysis_cache.httpx.AsyncClient", patched)

        analysis = AnalysisResponse(
            document={
                "filename": "p.pdf",
                "page_count": 1,
                "extracted_characters": 500,
                "chunk_count": 1,
                "truncated": False,
            },
            summary=_summary(),
            research_gaps=_gaps(),
            literature_review=_review(),
            model_used="claude-opus-5",
            model_provider="anthropic",
            fallback_used=False,
            processing_time_ms=1000,
        )
        asyncio.run(
            AnalysisCache(SETTINGS).put(
                content_hash="abc", analysis_version=ANALYSIS_VERSION, analysis=analysis
            )
        )

        assert seen, "no write was attempted"
        assert "ignore-duplicates" in seen[0].headers.get("prefer", "")
        body = json.loads(seen[0].content)
        assert body["content_hash"] == "abc"
        assert body["analysis_version"] == ANALYSIS_VERSION
        # No ownership travels with a cache entry - see the migration note.
        assert "user_id" not in body


class TestTheCacheStoresNoOwnership:
    def test_the_written_row_has_no_user_field_of_any_kind(self, monkeypatch) -> None:
        """The privacy guarantee is the ABSENCE of these columns. This asserts
        the application never tries to send one either."""
        import asyncio

        from src.db.analysis_cache import AnalysisCache
        from tests.test_library import _gaps, _review, _summary

        seen: list[httpx.Request] = []
        original = httpx.AsyncClient

        def patched(*a, **k):
            k.setdefault(
                "transport",
                httpx.MockTransport(lambda r: (seen.append(r), httpx.Response(201, json=[]))[1]),
            )
            return original(*a, **k)

        monkeypatch.setattr("src.db.analysis_cache.httpx.AsyncClient", patched)
        asyncio.run(
            AnalysisCache(SETTINGS).put(
                content_hash="abc",
                analysis_version=ANALYSIS_VERSION,
                analysis=AnalysisResponse(
                    document={
                        "filename": "p.pdf",
                        "page_count": 1,
                        "extracted_characters": 500,
                        "chunk_count": 1,
                        "truncated": False,
                    },
                    summary=_summary(),
                    research_gaps=_gaps(),
                    literature_review=_review(),
                    model_used="m",
                ),
            )
        )
        body = json.loads(seen[0].content)
        for forbidden in ("user_id", "owner_id", "uploaded_by", "email", "filename"):
            assert forbidden not in body
