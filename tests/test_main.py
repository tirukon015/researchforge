"""Tests for the Milestone 1 backend foundation.

WHAT A TEST IS (plain language)
-------------------------------
A test is a small piece of code that calls your real code and checks it did
the right thing. If someone later breaks the app by accident, these tests fail
immediately instead of the bug reaching users.

`TestClient` runs the FastAPI app *in memory*. No server needs to be started
and nothing touches the network, so the tests are fast and free.
"""

from fastapi.testclient import TestClient

from src import __version__
from src.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """The /health endpoint is what hosting platforms poll to check we're up."""

    def test_health_returns_200(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_reports_ok_status(self) -> None:
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_health_returns_all_expected_fields(self) -> None:
        body = client.get("/health").json()
        for field in ("status", "app_name", "version", "environment"):
            assert field in body, f"missing field: {field}"

    def test_health_version_matches_package_version(self) -> None:
        """Guards against the reported version drifting out of sync."""
        assert client.get("/health").json()["version"] == __version__

    def test_health_leaks_no_secrets(self) -> None:
        """A public endpoint must never expose configuration secrets.

        This test exists because health endpoints are unauthenticated — anyone
        on the internet can call them.
        """
        raw = client.get("/health").text.lower()
        for forbidden in ("key", "secret", "password", "token", "postgresql://"):
            assert forbidden not in raw, f"health response leaked '{forbidden}'"


class TestRootEndpoint:
    def test_root_returns_200(self) -> None:
        assert client.get("/").status_code == 200

    def test_root_describes_the_api(self) -> None:
        body = client.get("/").json()
        assert "Research Paper Assistant" in body["message"]
        assert body["health_url"] == "/health"


class TestApplicationSetup:
    """Sanity checks on how the app itself is wired together."""

    def test_openapi_schema_is_generated(self) -> None:
        """If this passes, the interactive /docs page will work."""
        schema = client.get("/openapi.json").json()
        assert "/health" in schema["paths"]

    def test_unknown_route_returns_404(self) -> None:
        assert client.get("/this-route-does-not-exist").status_code == 404
