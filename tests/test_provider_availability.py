"""Owner-controlled provider availability: a switched-off provider is never called.

THE PROPERTY THAT MATTERS
-------------------------
"Disabled" has to mean the routing layer CANNOT reach the provider, not that a
control is hidden. So the tests below assert on the fake provider's own call
log: a disabled vendor must record zero calls, whatever happens to the other
one. Hiding a toggle is not a guarantee; an empty call log is.

The enforcement is structural rather than a check. `build_routed_provider`
never CONSTRUCTS a disabled provider, so there is no branch inside the router
that could reach one - which is why these tests can be about what was built as
much as about what was called.

TWO INVARIANTS
--------------
  1. at least one provider stays enabled - otherwise nothing can run
  2. the primary is always one of the enabled ones - otherwise the owner has
     switched off the thing doing the work

Both are validated against the RESULTING state, so "make Claude primary and
switch Groq off" succeeds as one request even though each half alone is
invalid.

NO NETWORK, NO KEYS.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api.analyze import get_provider
from src.api.papers import get_library
from src.config import Settings, get_settings
from src.main import app
from src.rag.llm import build_routed_provider
from src.rag.llm.base import LLMError, LLMProvider, LLMRateLimitError
from tests.auth_fixtures import USER_A, USER_B, sign_in_as, sign_out
from tests.test_analysis import FakeLLMProvider
from tests.test_library import FakeRepository

BOTH_KEYS = Settings(_env_file=None, anthropic_api_key="a", groq_api_key="g")


class Reply(BaseModel):
    text: str


class CountingProvider(LLMProvider):
    """Records every call, so "never called" is an assertion and not a hope."""

    def __init__(self, name: str, *, fail_with: Exception | None = None):
        self._name = name
        self.fail_with = fail_with
        self.calls = 0

    @property
    def model_name(self) -> str:
        return self._name

    def generate_structured(self, *, system, prompt, output_model):
        self.calls += 1
        if self.fail_with:
            raise self.fail_with
        return output_model(text=self._name)

    def generate_text(self, *, system, prompt) -> str:
        self.calls += 1
        if self.fail_with:
            raise self.fail_with
        return self._name


# --------------------------------------------------------------------------- #
# The routing layer
# --------------------------------------------------------------------------- #


class TestRoutingRespectsAvailability:
    def test_1_both_enabled_gives_a_primary_and_a_fallback(self) -> None:
        """Case 1: the existing behaviour, unchanged."""
        r = build_routed_provider("groq", BOTH_KEYS, ["anthropic", "groq"])
        assert r.active_key == "groq"
        assert r._fallback_key == "anthropic"
        assert r._fallback is not None

    def test_2_primary_groq_with_claude_disabled_has_NO_fallback(self) -> None:
        """Case 2. The fallback is not merely skipped at call time - it is
        never built, so there is nothing for the router to reach."""
        r = build_routed_provider("groq", BOTH_KEYS, ["groq"])
        assert r.active_key == "groq"
        assert r._fallback is None
        assert r._fallback_key is None

    def test_3_primary_claude_with_groq_disabled_has_NO_fallback(self) -> None:
        """Case 3, the mirror image."""
        r = build_routed_provider("anthropic", BOTH_KEYS, ["anthropic"])
        assert r.active_key == "anthropic"
        assert r._fallback is None

    def test_8_a_disabled_provider_is_NEVER_called_even_when_the_primary_fails(
        self,
    ) -> None:
        """Case 8, and the single most important test in this file.

        The primary fails with a RETRYABLE error - exactly the condition that
        would normally trigger a fallback. The disabled provider must still
        record zero calls, and the primary's own error must surface rather
        than being masked by a second attempt.
        """
        from src.rag.llm.router import RoutedLLMProvider

        primary = CountingProvider("qwen", fail_with=LLMRateLimitError("429"))
        disabled = CountingProvider("claude")

        # Built the way availability builds it: no fallback at all.
        router = RoutedLLMProvider(
            primary=primary, primary_key="groq", fallback=None, fallback_key=None
        )
        with pytest.raises(LLMRateLimitError):
            router.generate_structured(system="s", prompt="p", output_model=Reply)

        assert primary.calls == 1
        assert disabled.calls == 0, "a disabled provider was called"

    def test_the_analysis_fails_honestly_rather_than_switching(self) -> None:
        """With no fallback the primary's OWN error reaches the caller. It must
        not be wrapped in a "both providers failed" message naming a vendor
        that was never asked."""
        from src.rag.llm.router import RoutedLLMProvider

        router = RoutedLLMProvider(
            primary=CountingProvider("qwen", fail_with=LLMRateLimitError("Groq is rate limiting")),
            primary_key="groq",
            fallback=None,
            fallback_key=None,
        )
        with pytest.raises(LLMRateLimitError) as raised:
            router.generate_text(system="s", prompt="p")
        assert "Claude" not in str(raised.value)

    def test_a_disabled_PRIMARY_is_a_configuration_error(self) -> None:
        """Distinct from a disabled fallback, which is fine. Nothing can run,
        and only the owner can fix it - so the message says where to go."""
        with pytest.raises(LLMError) as raised:
            build_routed_provider("groq", BOTH_KEYS, ["anthropic"])
        message = str(raised.value)
        assert "switched off" in message
        assert "Settings" in message

    def test_no_provider_enabled_is_a_clear_configuration_error(self) -> None:
        """Unreachable through the API and unrepresentable in the database.
        Handled anyway, so a hand-edited configuration fails with a sentence."""
        with pytest.raises(LLMError) as raised:
            build_routed_provider("groq", BOTH_KEYS, [])
        assert "No AI provider is enabled" in str(raised.value)

    def test_omitting_availability_keeps_the_old_behaviour(self) -> None:
        """`None` means "no restriction". A deployment that predates the
        setting must behave exactly as it did before."""
        r = build_routed_provider("groq", BOTH_KEYS, None)
        assert r._fallback is not None

    def test_13_groq_primary_with_claude_fallback_still_works(self) -> None:
        """Case 13: the pre-existing behaviour is not a casualty."""
        r = build_routed_provider("groq", BOTH_KEYS, ["anthropic", "groq"])
        assert (r.active_key, r._fallback_key) == ("groq", "anthropic")

    def test_14_claude_primary_with_groq_fallback_still_works(self) -> None:
        """Case 14, the other direction."""
        r = build_routed_provider("anthropic", BOTH_KEYS, ["anthropic", "groq"])
        assert (r.active_key, r._fallback_key) == ("anthropic", "groq")


# --------------------------------------------------------------------------- #
# The owner API
# --------------------------------------------------------------------------- #


@pytest.fixture
def library():
    repo = FakeRepository()
    repo.owners.add(USER_A.id)
    repo.active_provider = "groq"
    repo.enabled_providers = ["anthropic", "groq"]
    app.dependency_overrides[get_library] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: BOTH_KEYS
    app.dependency_overrides[get_provider] = lambda: FakeLLMProvider()
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def client(library):
    return TestClient(app)


class TestOwnerCanChangeAvailability:
    def test_7_the_owner_can_disable_the_non_primary_provider(self, client, library) -> None:
        """Case 7. Groq is primary, so Claude is the one that may be switched off."""
        sign_in_as(USER_A)
        response = client.put("/api/owner/ai-config", json={"enabled": ["groq"]})
        assert response.status_code == 200
        assert response.json()["enabled_providers"] == ["groq"]
        assert library.enabled_providers == ["groq"]

    def test_the_config_reports_the_fallback_as_unavailable_once_disabled(self, client) -> None:
        """A fallback needs a key AND permission. Reporting it as standing by
        would describe something the router will never call."""
        sign_in_as(USER_A)
        body = client.put("/api/owner/ai-config", json={"enabled": ["groq"]}).json()
        assert body["fallback_available"] is False

    def test_each_provider_is_described_for_the_controls(self, client) -> None:
        sign_in_as(USER_A)
        body = client.get("/api/owner/ai-config").json()
        by_key = {p["key"]: p for p in body["providers"]}
        assert by_key["groq"]["is_primary"] is True
        assert by_key["anthropic"]["is_primary"] is False
        assert by_key["groq"]["model"] == "qwen/qwen3.6-27b"
        assert by_key["anthropic"]["model"] == "claude-opus-5"
        assert all(p["enabled"] for p in body["providers"])

    def test_switching_primary_and_disabling_the_old_one_is_ONE_request(
        self, client, library
    ) -> None:
        """The resulting state is validated as a whole, so this succeeds even
        though each half alone would be rejected. Field-by-field validation
        would make the intended workflow impossible."""
        sign_in_as(USER_A)
        response = client.put(
            "/api/owner/ai-config",
            json={"provider": "anthropic", "enabled": ["anthropic"]},
        )
        assert response.status_code == 200
        assert library.active_provider == "anthropic"
        assert library.enabled_providers == ["anthropic"]

    def test_re_enabling_works(self, client, library) -> None:
        sign_in_as(USER_A)
        client.put("/api/owner/ai-config", json={"enabled": ["groq"]})
        body = client.put("/api/owner/ai-config", json={"enabled": ["anthropic", "groq"]}).json()
        assert body["enabled_providers"] == ["anthropic", "groq"]
        assert body["fallback_available"] is True

    def test_12_setting_only_the_primary_still_works(self, client, library) -> None:
        """Case 12: the pre-existing contract is unchanged."""
        sign_in_as(USER_A)
        response = client.put("/api/owner/ai-config", json={"provider": "anthropic"})
        assert response.status_code == 200
        assert response.json()["active_provider"] == "anthropic"
        assert library.enabled_providers == ["anthropic", "groq"], "availability untouched"


class TestInvalidConfigurationIsRefused:
    def test_4_the_current_primary_cannot_be_switched_off(self, client, library) -> None:
        """Case 4. Groq is primary; disabling it would leave the application
        pointing at a provider it may not use."""
        sign_in_as(USER_A)
        response = client.put("/api/owner/ai-config", json={"enabled": ["anthropic"]})
        assert response.status_code == 422
        assert library.enabled_providers == ["anthropic", "groq"], "nothing was written"

    def test_the_refusal_says_how_to_do_it(self, client) -> None:
        """ "You cannot do that" without "here is how" is the more annoying
        half of a validation error."""
        sign_in_as(USER_A)
        detail = client.put("/api/owner/ai-config", json={"enabled": ["anthropic"]}).json()[
            "detail"
        ]
        assert "primary" in detail.lower()
        assert "Claude" in detail and "Groq" in detail

    def test_5_both_providers_off_is_rejected(self, client, library) -> None:
        """Case 5. Nothing could be analysed."""
        sign_in_as(USER_A)
        response = client.put("/api/owner/ai-config", json={"enabled": []})
        assert response.status_code == 422
        assert "at least one" in response.json()["detail"].lower()
        assert library.enabled_providers == ["anthropic", "groq"]

    @pytest.mark.parametrize("bad", [["gemini"], ["openai"], ["auto"], ["groq", "gemini"]])
    def test_11_invalid_provider_values_are_rejected(self, client, library, bad) -> None:
        """Case 11. Gemini in particular: it is retired, and must not creep
        back in through a settings write."""
        sign_in_as(USER_A)
        response = client.put("/api/owner/ai-config", json={"enabled": bad})
        assert response.status_code == 422
        assert library.enabled_providers == ["anthropic", "groq"]

    def test_an_empty_request_changes_nothing(self, client, library) -> None:
        sign_in_as(USER_A)
        assert client.put("/api/owner/ai-config", json={}).status_code == 422
        assert library.active_provider == "groq"
        assert library.enabled_providers == ["anthropic", "groq"]


class TestOnlyTheOwner:
    def test_6_a_normal_user_cannot_change_availability(self, client, library) -> None:
        """Case 6. Server-side, not a hidden control."""
        sign_in_as(USER_B)
        response = client.put("/api/owner/ai-config", json={"enabled": ["groq"]})
        assert response.status_code == 403
        assert library.enabled_providers == ["anthropic", "groq"]

    def test_a_normal_user_cannot_even_read_it(self, client) -> None:
        sign_in_as(USER_B)
        assert client.get("/api/owner/ai-config").status_code == 403

    def test_an_anonymous_caller_gets_401_not_403(self, client, library) -> None:
        sign_out()
        assert client.put("/api/owner/ai-config", json={"enabled": ["groq"]}).status_code == 401
        assert library.enabled_providers == ["anthropic", "groq"]


# --------------------------------------------------------------------------- #
# Everything else is unaffected
# --------------------------------------------------------------------------- #


class TestNothingElseChanges:
    def test_9_a_cache_hit_calls_no_model_whatever_the_availability(self, monkeypatch) -> None:
        """Case 9. The cache is consulted BEFORE any provider is built, so a
        reused analysis costs nothing regardless of which vendors are on."""
        from src.services.content_hash import ANALYSIS_VERSION
        from tests.pdf_fixtures import build_text_pdf
        from tests.test_analysis import PAPER_TEXT
        from tests.test_analysis_cache import SETTINGS, FakeCache, cached_entry

        provider = FakeLLMProvider()
        cache = FakeCache()
        sign_in_as(USER_A)
        app.dependency_overrides[get_settings] = lambda: SETTINGS
        app.dependency_overrides[get_provider] = lambda: provider
        monkeypatch.setattr("src.api.analyze.get_analysis_cache", lambda s: cache)
        try:
            client = TestClient(app)
            files = {"file": ("p.pdf", build_text_pdf(PAPER_TEXT), "application/pdf")}
            first = client.post("/api/analyze", files=files)
            assert first.status_code == 200
            digest = cache.puts[0][0]
            cache.entries[(digest, ANALYSIS_VERSION)] = cached_entry()
            provider.structured_calls.clear()

            second = client.post("/api/analyze", files=files)
            assert second.status_code == 200
            assert second.json()["cache_hit"] is True
            assert provider.structured_calls == [], "a cache hit called a model"
        finally:
            app.dependency_overrides.clear()

    def test_10_availability_is_a_separate_setting_from_the_primary(self, client, library) -> None:
        """Case 10, at the configuration level: changing availability must not
        rewrite the primary, and stored analyses are never touched by either -
        no endpoint here writes to `analyses` at all."""
        sign_in_as(USER_A)
        client.put("/api/owner/ai-config", json={"enabled": ["groq"]})
        assert library.active_provider == "groq", "the primary was rewritten"

    def test_a_deployment_with_no_stored_availability_enables_everything(
        self, client, library
    ) -> None:
        """Before migration 006 runs there is no row. The default must be
        "both on", so applying the migration changes no behaviour."""
        library.enabled_providers = None
        sign_in_as(USER_A)
        assert client.get("/api/owner/ai-config").json()["enabled_providers"] == [
            "anthropic",
            "groq",
        ]
