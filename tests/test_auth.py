"""The door: who may reach the API at all.

WHAT THIS FILE COVERS
---------------------
That every route touching research data refuses an unauthenticated caller, and
that the two public routes stay public. It is deliberately separate from
`test_ownership.py`, which covers the different question of what a caller who
IS signed in may see.

NO NETWORK, NO REAL ACCOUNTS. `require_user` normally asks Supabase to verify
an access token; here the HTTP call is intercepted, so the verification logic
runs for real against replies Supabase would actually send.
"""

import asyncio

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.auth import (
    AuthUser,
    bearer_token,
    require_user,
    reset_auth_cache,
    verify_token,
)
from src.config import Settings, get_settings
from src.main import app
from tests.auth_fixtures import USER_A, sign_in_as, sign_out

URL = "https://example-project.supabase.co"
ANON = "not-a-real-anon-key-for-tests-only"
TOKEN = "not-a-real-access-token-for-tests-only"

# Every route that reads, writes, or spends money on a person's behalf.
# Parametrised as one list so a route added later without authentication shows
# up here as an omission rather than as a silent hole in production.
PROTECTED = [
    ("GET", "/api/papers"),
    ("GET", "/api/papers/stats"),
    ("GET", "/api/papers/some-paper-id"),
    ("POST", "/api/papers"),
    ("DELETE", "/api/papers/some-paper-id"),
    ("GET", "/api/reviews"),
    ("GET", "/api/reviews/some-review-id"),
    ("POST", "/api/reviews/cross"),
    ("DELETE", "/api/reviews/some-review-id"),
    ("POST", "/api/analyze"),
]


def settings() -> Settings:
    return Settings(_env_file=None, supabase_url=URL, supabase_anon_key=ANON)


def run(coro):
    """Drive one coroutine. Avoids adding an async test plugin."""
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean():
    """No test may inherit another's identity or cached verification."""
    app.dependency_overrides.clear()
    reset_auth_cache()
    yield
    app.dependency_overrides.clear()
    reset_auth_cache()


@pytest.fixture
def gotrue(monkeypatch):
    """Intercept the call `verify_token` makes to Supabase's /auth/v1/user."""
    holder: dict[str, httpx.MockTransport] = {}
    original = httpx.AsyncClient

    def patched(*args, **kwargs):
        if "transport" not in kwargs and "mock" in holder:
            kwargs["transport"] = holder["mock"]
        return original(*args, **kwargs)

    monkeypatch.setattr("src.api.auth.httpx.AsyncClient", patched)

    def install(handler):
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        holder["mock"] = httpx.MockTransport(recording)
        return seen

    return install


# --------------------------------------------------------------------------- #
# Refusing anonymous callers
# --------------------------------------------------------------------------- #


class TestProtectedRoutes:
    @pytest.mark.parametrize(("method", "path"), PROTECTED)
    def test_no_credential_is_refused_with_401(self, method, path) -> None:
        """The whole point of the feature, stated once per route.

        Before authentication these answered 200 with somebody's papers in the
        body. A 401 here is what makes "your library" a true phrase.
        """
        sign_out()
        app.dependency_overrides[get_settings] = settings
        response = TestClient(app).request(method, path)
        assert response.status_code == 401

    @pytest.mark.parametrize(("method", "path"), PROTECTED)
    def test_a_refusal_never_carries_data(self, method, path) -> None:
        """A 401 body must contain the reason and nothing else. A route that
        rendered a list and *then* checked the token would leak on the way to
        refusing."""
        sign_out()
        app.dependency_overrides[get_settings] = settings
        body = TestClient(app).request(method, path).json()
        assert set(body) == {"detail"}
        assert "sign in" in body["detail"].lower()

    def test_the_refusal_names_the_scheme_the_client_should_use(self) -> None:
        """WWW-Authenticate lets a client tell "you sent nothing" apart from
        "what you sent was refused" without reading prose."""
        sign_out()
        app.dependency_overrides[get_settings] = settings
        response = TestClient(app).get("/api/papers")
        assert response.headers["www-authenticate"] == "Bearer"

    @pytest.mark.parametrize(
        "header",
        [
            "",
            "Bearer",
            "Bearer   ",
            "Basic dXNlcjpwYXNz",
            "not-a-scheme token",
            "token-with-no-scheme",
        ],
    )
    def test_a_malformed_authorization_header_is_not_a_credential(self, header) -> None:
        """Anything that is not a non-empty Bearer token is treated as absent,
        never passed through to be verified as though it might work."""
        sign_out()
        app.dependency_overrides[get_settings] = settings
        response = TestClient(app).get("/api/papers", headers={"Authorization": header})
        assert response.status_code == 401


class TestPublicRoutes:
    """Two routes must stay reachable without an account.

    /health is what the hosting platform polls, and it cannot hold a token.
    / describes the API. Both are also what the public landing page relies on
    to say whether the service is up before anyone has signed in.
    """

    @pytest.mark.parametrize("path", ["/", "/health"])
    def test_is_reachable_anonymously(self, path) -> None:
        sign_out()
        assert TestClient(app).get(path).status_code == 200

    def test_health_reports_whether_accounts_are_configured(self) -> None:
        sign_out()
        app.dependency_overrides[get_settings] = settings
        assert TestClient(app).get("/health").json()["auth"] is True

    def test_health_says_so_when_accounts_are_not_configured(self) -> None:
        """Without this the sign-in page would offer a form that cannot
        succeed, and the failure would read as "wrong password"."""
        sign_out()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        assert TestClient(app).get("/health").json()["auth"] is False

    def test_health_still_leaks_no_url_and_no_key(self) -> None:
        sign_out()
        app.dependency_overrides[get_settings] = settings
        body = TestClient(app).get("/health").text
        assert URL not in body
        assert ANON not in body


# --------------------------------------------------------------------------- #
# Reading the header
# --------------------------------------------------------------------------- #


class TestBearerToken:
    def test_extracts_the_token(self) -> None:
        assert bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_the_scheme_is_case_insensitive(self) -> None:
        """RFC 7235 says the scheme is case-insensitive, and real clients
        differ. Rejecting `bearer` would fail for a reason nobody could see."""
        assert bearer_token("bearer abc") == "abc"
        assert bearer_token("BEARER abc") == "abc"

    @pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer ", "Basic abc", "abc"])
    def test_anything_else_is_no_token(self, header) -> None:
        assert bearer_token(header) is None


# --------------------------------------------------------------------------- #
# Verifying the token against Supabase
# --------------------------------------------------------------------------- #

USER_PAYLOAD = {
    "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "email": "researcher@example.test",
    "user_metadata": {"full_name": "A Researcher"},
}


class TestVerifyToken:
    def test_a_valid_token_becomes_a_user(self, gotrue) -> None:
        gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        user = run(verify_token(TOKEN, settings()))
        assert user.id == USER_PAYLOAD["id"]
        assert user.email == "researcher@example.test"
        assert user.full_name == "A Researcher"

    def test_the_token_is_carried_on_the_user(self, gotrue) -> None:
        """The data layer needs it: the library is read with the USER'S OWN
        credentials so Postgres applies their row-level policies. Dropping it
        here would force the repository back onto a key that bypasses them."""
        gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        assert run(verify_token(TOKEN, settings())).token == TOKEN

    def test_the_request_carries_the_public_key_and_the_users_token(self, gotrue) -> None:
        seen = gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        run(verify_token(TOKEN, settings()))
        assert seen[0].url.path.endswith("/auth/v1/user")
        assert seen[0].headers["apikey"] == ANON
        assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"

    @pytest.mark.parametrize("status", [401, 403])
    def test_a_rejected_token_is_401_and_says_to_sign_in_again(self, gotrue, status) -> None:
        gotrue(lambda r: httpx.Response(status, json={"message": "invalid JWT"}))
        with pytest.raises(HTTPException) as raised:
            run(verify_token(TOKEN, settings()))
        assert raised.value.status_code == 401
        assert "expired" in raised.value.detail.lower()

    def test_the_refusal_never_echoes_the_token(self, gotrue) -> None:
        gotrue(lambda r: httpx.Response(401, json={"message": "invalid JWT"}))
        with pytest.raises(HTTPException) as raised:
            run(verify_token(TOKEN, settings()))
        assert TOKEN not in raised.value.detail
        assert ANON not in raised.value.detail

    def test_an_unreachable_auth_service_is_503_not_401(self, gotrue) -> None:
        """A sign-in service that is down has not rejected anybody. Answering
        401 would send the user to a login form equally unable to respond, and
        would look to them like their password stopped working."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host", request=request)

        gotrue(handler)
        with pytest.raises(HTTPException) as raised:
            run(verify_token(TOKEN, settings()))
        assert raised.value.status_code == 503

    def test_a_timeout_is_503_not_401(self, gotrue) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        gotrue(handler)
        with pytest.raises(HTTPException) as raised:
            run(verify_token(TOKEN, settings()))
        assert raised.value.status_code == 503

    def test_a_success_with_no_account_id_is_503_not_a_user(self, gotrue) -> None:
        """A 200 with no id is a broken contract, not a valid anonymous user.
        Accepting it would produce an AuthUser whose id is "", and `user_id =
        auth.uid()` would then quietly match nothing forever."""
        gotrue(lambda r: httpx.Response(200, json={"email": "x@example.test"}))
        with pytest.raises(HTTPException) as raised:
            run(verify_token(TOKEN, settings()))
        assert raised.value.status_code == 503

    def test_accounts_not_configured_is_503_and_names_the_variables(self) -> None:
        with pytest.raises(HTTPException) as raised:
            run(verify_token(TOKEN, Settings(_env_file=None)))
        assert raised.value.status_code == 503
        assert "SUPABASE_ANON_KEY" in raised.value.detail

    def test_a_name_falls_back_to_the_email_when_none_was_given(self, gotrue) -> None:
        """An account created outside our sign-up form has no full_name. The
        interface must still greet them with something rather than a blank."""
        gotrue(
            lambda r: httpx.Response(
                200, json={"id": "x", "email": "nameless@example.test", "user_metadata": {}}
            )
        )
        assert run(verify_token(TOKEN, settings())).full_name == "nameless@example.test"

    def test_the_dashboards_metadata_key_is_understood_too(self, gotrue) -> None:
        """Supabase's own dashboard writes `name`, our form writes `full_name`."""
        gotrue(
            lambda r: httpx.Response(
                200,
                json={
                    "id": "x",
                    "email": "e@example.test",
                    "user_metadata": {"name": "Dr Who"},
                },
            )
        )
        assert run(verify_token(TOKEN, settings())).full_name == "Dr Who"


class TestVerificationCache:
    def test_a_repeat_check_does_not_re_ask_supabase(self, gotrue) -> None:
        """One page load makes several API calls. Verifying each separately
        would put a round trip in front of every one of them."""
        seen = gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        run(verify_token(TOKEN, settings()))
        run(verify_token(TOKEN, settings()))
        run(verify_token(TOKEN, settings()))
        assert len(seen) == 1

    def test_two_different_tokens_are_checked_separately(self, gotrue) -> None:
        """The cache is keyed by token. If it were not, one user's verification
        would answer another user's request - which is the whole failure this
        feature exists to prevent, reintroduced as an optimisation."""
        seen = gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        run(verify_token("token-one", settings()))
        run(verify_token("token-two", settings()))
        assert len(seen) == 2

    def test_a_rejected_token_is_never_cached(self, gotrue) -> None:
        """Caching a failure would be harmless; caching would also mean a token
        that starts working (clock skew, a just-issued refresh) stays refused.
        Only successes are kept."""
        seen = gotrue(lambda r: httpx.Response(401, json={"message": "no"}))
        for _ in range(2):
            with pytest.raises(HTTPException):
                run(verify_token(TOKEN, settings()))
        assert len(seen) == 2


class TestRequireUser:
    def test_a_valid_bearer_header_resolves_to_the_user(self, gotrue) -> None:
        gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        user = run(require_user(f"Bearer {TOKEN}", settings()))
        assert isinstance(user, AuthUser)
        assert user.id == USER_PAYLOAD["id"]

    def test_a_missing_header_is_401_without_asking_supabase(self, gotrue) -> None:
        """Refused locally. Sending an absent credential to be verified would
        add a network round trip to every unauthenticated request, which is
        exactly what a flood of them would be made of."""
        seen = gotrue(lambda r: httpx.Response(200, json=USER_PAYLOAD))
        with pytest.raises(HTTPException) as raised:
            run(require_user(None, settings()))
        assert raised.value.status_code == 401
        assert seen == []


class TestSignedInRequestsStillWork:
    """The refusals above must not have been achieved by breaking the app."""

    def test_a_signed_in_caller_reaches_the_route(self) -> None:
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        # 503: no database configured in this test. The point is that it is no
        # longer 401 - the caller got past the door.
        assert TestClient(app).get("/api/papers").status_code == 503
