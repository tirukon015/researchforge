"""Owner-only AI configuration: who may change it, and who may not.

THE THREE ANSWERS THAT MUST DIFFER
----------------------------------
    no account          401
    ordinary account    403
    owner               200

A test suite that only checked the owner path would pass while the endpoint
was wide open, so the ordinary-user refusals are the point of this file.

WHAT THIS CANNOT TEST, AND WHY THAT IS FINE
-------------------------------------------
Authorisation is enforced twice: here in the API, and again by the Row Level
Security policies in migration 004, which refuse a non-owner's write to
`system_settings` even if the API layer were bypassed entirely. Only the first
layer is reachable offline. The second is verified against the live database,
because a fake that modelled it would only prove the fake agrees with itself.

NO DATABASE, NO NETWORK, NO KEYS.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.analyze import get_provider
from src.api.papers import get_library
from src.config import Settings, get_settings
from src.main import app
from tests.auth_fixtures import USER_A, USER_B, sign_in_as, sign_out
from tests.test_analysis import FakeLLMProvider
from tests.test_library import FakeRepository


@pytest.fixture
def library():
    """A library where USER_A is the owner and USER_B is an ordinary user."""
    repo = FakeRepository()
    repo.owners.add(USER_A.id)
    app.dependency_overrides[get_library] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def client(library):
    return TestClient(app)


OWNER_ROUTES = [
    ("GET", "/api/owner/ai-config"),
    ("PUT", "/api/owner/ai-config"),
]


# --------------------------------------------------------------------------- #
# Anonymous
# --------------------------------------------------------------------------- #


class TestUnauthenticated:
    @pytest.mark.parametrize(("method", "path"), [*OWNER_ROUTES, ("GET", "/api/owner/status")])
    def test_every_owner_route_refuses_an_anonymous_caller(self, client, method, path) -> None:
        sign_out()
        response = client.request(method, path, json={"provider": "groq"})
        assert response.status_code == 401

    def test_the_refusal_is_401_and_not_403(self, client) -> None:
        """Different facts, different advice. 401 means "sign in"; 403 means
        "this is not yours to change". Conflating them tells a signed-out
        person their account lacks a privilege it may well have."""
        sign_out()
        assert client.get("/api/owner/ai-config").status_code == 401


# --------------------------------------------------------------------------- #
# Signed in, but not the owner
# --------------------------------------------------------------------------- #


class TestOrdinaryUserIsRefused:
    @pytest.mark.parametrize(("method", "path"), OWNER_ROUTES)
    def test_a_normal_user_gets_403(self, client, method, path) -> None:
        sign_in_as(USER_B)
        response = client.request(method, path, json={"provider": "groq"})
        assert response.status_code == 403

    def test_the_403_explains_without_alarming(self, client) -> None:
        sign_in_as(USER_B)
        detail = client.get("/api/owner/ai-config").json()["detail"]
        assert "owner" in detail.lower()
        # Reassures them their own work is untouched: this is a permissions
        # boundary, not a fault they caused.
        assert "library is unaffected" in detail

    def test_a_normal_user_cannot_change_the_provider(self, client, library) -> None:
        """The one that matters. Frontend hiding is not a boundary; this is."""
        sign_in_as(USER_B)
        assert client.put("/api/owner/ai-config", json={"provider": "groq"}).status_code == 403
        assert library.active_provider is None

    def test_a_normal_user_is_told_they_are_not_the_owner(self, client) -> None:
        """`/status` answers 200 with `false` rather than 403, so the Settings
        page can simply omit the section. A 403 here would make the ordinary
        case look like an error."""
        sign_in_as(USER_B)
        response = client.get("/api/owner/status")
        assert response.status_code == 200
        assert response.json() == {"is_owner": False}


# --------------------------------------------------------------------------- #
# The owner
# --------------------------------------------------------------------------- #


class TestOwner:
    def test_the_owner_is_recognised(self, client) -> None:
        sign_in_as(USER_A)
        assert client.get("/api/owner/status").json() == {"is_owner": True}

    def test_the_owner_can_read_the_configuration(self, client) -> None:
        sign_in_as(USER_A)
        response = client.get("/api/owner/ai-config")
        assert response.status_code == 200
        body = response.json()
        assert body["active_provider"] == "anthropic"
        assert body["fallback_provider"] == "groq"

    def test_choosing_a_provider_makes_the_other_one_the_fallback(self, client) -> None:
        sign_in_as(USER_A)
        body = client.put("/api/owner/ai-config", json={"provider": "groq"}).json()
        assert body["active_provider"] == "groq"
        assert body["fallback_provider"] == "anthropic"

    def test_the_choice_is_persisted(self, client, library) -> None:
        sign_in_as(USER_A)
        client.put("/api/owner/ai-config", json={"provider": "groq"})
        assert library.active_provider == "groq"
        assert library.provider_set_by == USER_A.id

    def test_the_labels_are_human_readable(self, client) -> None:
        sign_in_as(USER_A)
        body = client.get("/api/owner/ai-config").json()
        assert body["active_provider_label"] == "Claude"
        assert body["fallback_provider_label"] == "Groq Qwen 3.6 27B"

    def test_only_the_two_supported_providers_are_offered(self, client) -> None:
        """No "auto", and no Gemini. A third entry here would be a third
        option in the interface for something that is a pair by design."""
        sign_in_as(USER_A)
        assert client.get("/api/owner/ai-config").json()["available_providers"] == [
            "anthropic",
            "groq",
        ]

    @pytest.mark.parametrize("bad", ["auto", "gemini", "openai", "", "ANTHROPIC; DROP TABLE"])
    def test_an_unsupported_provider_is_refused(self, client, library, bad) -> None:
        sign_in_as(USER_A)
        response = client.put("/api/owner/ai-config", json={"provider": bad})
        assert response.status_code == 422
        assert library.active_provider is None

    def test_the_fallback_is_reported_as_unavailable_without_its_key(self, client) -> None:
        """A fallback with no API key is not a fallback, and the interface
        must not imply that one is standing by."""
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, anthropic_api_key="a", groq_api_key=""
        )
        assert client.get("/api/owner/ai-config").json()["fallback_available"] is False

    def test_the_fallback_is_available_when_both_keys_exist(self, client) -> None:
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, anthropic_api_key="a", groq_api_key="g"
        )
        assert client.get("/api/owner/ai-config").json()["fallback_available"] is True


# --------------------------------------------------------------------------- #
# The bootstrap path
# --------------------------------------------------------------------------- #


class TestOwnerEmailBootstrap:
    """`app_owners` starts empty, so OWNER_EMAIL can seed the first owner.

    It is compared against the email on a token Supabase has already verified,
    server-side. That is what separates it from a frontend email check, which
    would be worthless.
    """

    def test_a_matching_email_is_treated_as_the_owner(self, client) -> None:
        sign_in_as(USER_B)  # NOT in the owners table
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, owner_email=USER_B.email
        )
        assert client.get("/api/owner/status").json() == {"is_owner": True}

    def test_the_comparison_ignores_case_and_padding(self, client) -> None:
        sign_in_as(USER_B)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, owner_email=f"  {USER_B.email.upper()}  "
        )
        assert client.get("/api/owner/status").json() == {"is_owner": True}

    def test_a_different_email_is_not_the_owner(self, client) -> None:
        sign_in_as(USER_B)
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, owner_email="someone-else@example.test"
        )
        assert client.get("/api/owner/status").json() == {"is_owner": False}

    def test_an_unset_owner_email_grants_nothing(self, client) -> None:
        """The dangerous default. An empty OWNER_EMAIL must not match an
        account with an empty email, or a blank setting would make everyone
        an owner."""
        sign_in_as(USER_B)
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, owner_email="")
        assert client.get("/api/owner/status").json() == {"is_owner": False}

    def test_the_owners_table_still_works_without_the_variable(self, client) -> None:
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, owner_email="")
        assert client.get("/api/owner/status").json() == {"is_owner": True}


# --------------------------------------------------------------------------- #
# Failing safe
# --------------------------------------------------------------------------- #


class TestOwnershipFailsClosed:
    def test_an_unreadable_owners_table_denies_rather_than_grants(self, client, library) -> None:
        """If ownership cannot be established, the answer is no.

        Failing open would hand global configuration to every signed-in user
        during a database blip - a brief outage becoming a privilege
        escalation.
        """
        from src.db.repository import RepositoryError

        async def broken(_user_id: str) -> bool:
            raise RepositoryError("the library is unreachable")

        library.is_owner = broken
        sign_in_as(USER_A)
        assert client.get("/api/owner/status").json() == {"is_owner": False}
        assert client.get("/api/owner/ai-config").status_code == 403
