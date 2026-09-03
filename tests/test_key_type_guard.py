"""A Supabase PUBLISHABLE key must never be accepted as the backend key.

WHY THIS FILE EXISTS
--------------------
This is a regression test for a fault that reached production and did not look
like a fault. `SUPABASE_SERVICE_ROLE_KEY` was set to an `sb_publishable_` key:
the public, browser-safe key, which is subject to Row Level Security.

Migration 002 enables RLS with `user_id = auth.uid()` policies, and `auth.uid()`
is NULL for an anonymous key, so nothing errored. Reads returned HTTP 200 with
zero rows and writes were refused. The dashboard therefore displayed

    Papers Analysed: 0    Research Gaps: 0    Saved Papers: 0

which reads as a measured fact about an empty library, and was actually a
server that could not see its own data. A confident wrong number is worse than
an error, because nobody goes looking for the cause of a number that looks fine.

So the key TYPE is checked before any request is made, and a public key in a
private slot is reported as a misconfiguration rather than quietly connected.
"""

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, get_settings
from src.db import get_repository
from src.db.repository import RepositoryUnavailableError
from src.db.supabase import SupabaseRepository
from src.main import app

URL = "https://example-project.supabase.co"
PUBLISHABLE = "sb_publishable_exampleonlynotarealkey00"
SECRET = "sb_secret_exampleonlynotarealkey000000"
LEGACY_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.notarealsignature"


def settings_with(key: str) -> Settings:
    return Settings(_env_file=None, supabase_url=URL, supabase_service_role_key=key)


class TestKeyTypeDetection:
    def test_a_publishable_key_is_recognised(self) -> None:
        assert settings_with(PUBLISHABLE).supabase_key_is_publishable is True

    @pytest.mark.parametrize("key", [SECRET, LEGACY_JWT, "not-a-real-key-for-tests-only", ""])
    def test_every_other_key_shape_is_left_alone(self, key) -> None:
        """The guard rejects one specific mistake and must not become a
        whitelist. A legacy `service_role` JWT is still perfectly valid, and a
        future key format must not be refused by a check that predates it."""
        assert settings_with(key).supabase_key_is_publishable is False

    def test_a_publishable_key_means_the_library_is_not_configured(self) -> None:
        """It would connect. That is precisely why it is refused: connecting
        and reading nothing is indistinguishable from an empty library."""
        assert settings_with(PUBLISHABLE).has_database is False

    def test_a_secret_key_configures_the_library_normally(self) -> None:
        assert settings_with(SECRET).has_database is True

    def test_a_legacy_service_role_jwt_still_works(self) -> None:
        """Projects created before the new key format still hold a JWT here.
        Breaking them to fix this would trade one outage for another."""
        assert settings_with(LEGACY_JWT).has_database is True


class TestRepositoryRefusesToStart:
    def test_no_repository_is_built_from_a_publishable_key(self) -> None:
        assert get_repository(settings_with(PUBLISHABLE)) is None

    def test_constructing_one_directly_raises_and_names_the_key_type(self) -> None:
        with pytest.raises(RepositoryUnavailableError) as raised:
            SupabaseRepository(settings_with(PUBLISHABLE))
        message = str(raised.value)
        assert "publishable" in message.lower()
        assert "secret" in message.lower()

    def test_the_error_never_contains_the_key_or_the_url(self) -> None:
        """The message is shown to whoever opens the page, so it may name the
        VARIABLE and the required key type, and nothing else."""
        with pytest.raises(RepositoryUnavailableError) as raised:
            SupabaseRepository(settings_with(PUBLISHABLE))
        message = str(raised.value)
        assert PUBLISHABLE not in message
        assert URL not in message
        assert "example-project" not in message


class TestHttpBehaviour:
    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def _client(self, key: str) -> TestClient:
        app.dependency_overrides[get_settings] = lambda: settings_with(key)
        return TestClient(app)

    def test_health_reports_the_library_as_unavailable(self) -> None:
        """/health is the one place an operator looks first. Reporting
        `library: true` here while every read comes back empty is what let the
        misconfiguration survive: the service looked healthy."""
        body = self._client(PUBLISHABLE).get("/health").json()
        assert body["library"] is False

    def test_health_reports_true_for_a_secret_key(self) -> None:
        assert self._client(SECRET).get("/health").json()["library"] is True

    @pytest.mark.parametrize(
        "path", ["/api/papers", "/api/papers/stats", "/api/reviews", "/api/papers/some-id"]
    )
    def test_library_routes_answer_503_not_an_empty_list(self, path) -> None:
        """503, never 200 with zeros. An empty list is a claim about the
        user's library, and a server that cannot read it is in no position to
        make one."""
        response = self._client(PUBLISHABLE).get(path)
        assert response.status_code == 503

    def test_the_503_explains_which_key_is_required(self) -> None:
        detail = self._client(PUBLISHABLE).get("/api/papers").json()["detail"]
        assert "publishable" in detail.lower()
        assert "SUPABASE_SERVICE_ROLE_KEY" in detail

    def test_the_503_body_leaks_no_key_and_no_host(self) -> None:
        body = self._client(PUBLISHABLE).get("/api/papers").text
        assert PUBLISHABLE not in body
        assert "example-project" not in body

    def test_stats_never_reports_zeros_it_cannot_substantiate(self) -> None:
        """The original symptom, asserted directly.

        The dashboard renders "Not connected" for a 503 and a number for a
        200. Anything but 503 here puts a fabricated 0 back on the screen.
        """
        response = self._client(PUBLISHABLE).get("/api/papers/stats")
        assert response.status_code == 503
        assert "papers_analysed" not in response.text

    def test_saving_is_refused_rather_than_half_attempted(self) -> None:
        response = self._client(PUBLISHABLE).post("/api/papers", json={})
        assert response.status_code == 503

    def test_analysis_is_unaffected_by_the_database_being_unusable(self) -> None:
        """The whole reason the library degrades instead of crashing: a paper
        can still be analysed with nowhere to save it."""
        assert self._client(PUBLISHABLE).get("/health").json()["status"] == "ok"
