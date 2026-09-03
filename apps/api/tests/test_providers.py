"""Tests for the Sprint 3 provider layer (model profiles, selector, registry).

Mirrors the package-level testing pattern established by the Task Engine:
pure domain tests against `packages.providers` directly, with no
FastAPI dependency. Each test exercises a single, named behavior so
that the README's "testing strategy" section stays accurate.

No API keys, network access, or external services are required.
"""

from __future__ import annotations

import httpx
import pytest

from packages.providers.base import (
    AIProvider,
    ProviderCapability,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from packages.providers.exceptions import (
    InvalidModelProfileError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderError,
)
from packages.providers.models import ModelMetadata, ModelProfile
from packages.providers.registry import ProviderRegistry
from packages.providers.selector import ModelSelector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_profiles() -> dict[ModelProfile, ModelMetadata]:
    return {
        ModelProfile.AUTO: ModelMetadata(
            profile=ModelProfile.AUTO,
            description="deRek chooses the profile automatically.",
            recommended_for=[],
        ),
        ModelProfile.LIGHTNING: ModelMetadata(
            profile=ModelProfile.LIGHTNING,
            description="Optimized for speed — quick answers and lightweight tasks.",
            recommended_for=["quick", "simple", "fast", "short", "info"],
        ),
        ModelProfile.SUPER: ModelMetadata(
            profile=ModelProfile.SUPER,
            description="Balanced capability for general-purpose tasks.",
            recommended_for=["normal", "coding", "help", "general", "task"],
        ),
        ModelProfile.ULTRA: ModelMetadata(
            profile=ModelProfile.ULTRA,
            description="Complex reasoning — deep analysis and multi-step planning.",
            recommended_for=["complex", "architecture", "reasoning", "planning", "difficult"],
        ),
    }


def _selector() -> ModelSelector:
    return ModelSelector(profiles=_default_profiles())


# ===========================================================================
# ModelProfile: validation and serialization
# ===========================================================================


class TestModelProfile:
    def test_all_profiles_are_valid(self):
        assert ModelProfile.AUTO.value == "auto"
        assert ModelProfile.LIGHTNING.value == "lightning"
        assert ModelProfile.SUPER.value == "super"
        assert ModelProfile.ULTRA.value == "ultra"

    def test_round_trip_from_string(self):
        for profile in ModelProfile:
            assert ModelProfile(profile.value) is profile

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            ModelProfile("claude")

    def test_case_sensitive(self):
        with pytest.raises(ValueError):
            ModelProfile("AUTO")

    def test_serialization_json_value(self):
        import json
        payload = json.dumps({"model": ModelProfile.SUPER})
        assert "super" in payload

    def test_metadata_profile_field_type(self):
        meta = ModelMetadata(profile=ModelProfile.ULTRA, description="test")
        assert meta.profile is ModelProfile.ULTRA
        assert meta.description == "test"

    def test_metadata_defaults(self):
        meta = ModelMetadata(profile=ModelProfile.LIGHTNING, description="d")
        assert meta.recommended_for == []


# ===========================================================================
# ModelProfile exceptions
# ===========================================================================


class TestProviderExceptions:
    def test_invalid_model_profile_carries_offending_value(self):
        exc = InvalidModelProfileError("claude")
        assert exc.value == "claude"
        assert "claude" in str(exc)

    def test_provider_not_found_carries_name(self):
        exc = ProviderNotFoundError("openai")
        assert exc.provider_name == "openai"

    def test_provider_unavailable_is_provider_error(self):
        assert issubclass(ProviderUnavailableError, ProviderError)

    def test_invalid_model_profile_is_provider_error(self):
        assert issubclass(InvalidModelProfileError, ProviderError)
        assert issubclass(ProviderNotFoundError, ProviderError)

    def test_provider_not_found_message(self):
        exc = ProviderNotFoundError("anthropic")
        assert "anthropic" in str(exc)

    def test_provider_not_found_inheritance(self):
        assert issubclass(ProviderNotFoundError, ProviderError)

    def test_provider_unavailable_inheritance(self):
        assert issubclass(ProviderUnavailableError, ProviderError)

    def test_invalid_model_profile_inheritance(self):
        assert issubclass(InvalidModelProfileError, ProviderError)

    def test_canonical_hierarchy_is_single_tree(self):
        # Every provider exception must share the same base, defined in
        # packages.providers.exceptions only.
        assert ProviderError.__module__ == "packages.providers.exceptions"
        for cls in (
            ProviderUnavailableError,
            ProviderNotFoundError,
            InvalidModelProfileError,
        ):
            assert cls.__bases__[0] is ProviderError

    def test_no_duplicate_provider_error_in_base(self):
        # `packages.providers.base` must not re-define ProviderError.
        from packages.providers import base

        assert not hasattr(base, "ProviderError")
        assert not hasattr(base, "ProviderUnavailableError")


# ===========================================================================
# ModelSelector: AUTO selection
# ===========================================================================


class TestAutoSelection:
    def test_simple_question_selects_lightning(self):
        assert _selector().select("A quick simple question") is ModelProfile.LIGHTNING

    def test_quick_info_request_selects_lightning(self):
        assert _selector().select("Quick info on Docker") is ModelProfile.LIGHTNING

    def test_normal_question_selects_super(self):
        assert _selector().select("Help me write a sorting function") is ModelProfile.SUPER

    def test_coding_help_selects_super(self):
        assert _selector().select("General task: debug this error") is ModelProfile.SUPER

    def test_complex_reasoning_selects_ultra(self):
        assert _selector().select("Design a complex microservice architecture") is ModelProfile.ULTRA

    def test_multi_step_reasoning_selects_ultra(self):
        assert _selector().select("Complex architecture and deep reasoning") is ModelProfile.ULTRA

    def test_ambiguous_question_falls_back_to_super(self):
        assert _selector().select("Hello") is ModelProfile.SUPER

    def test_empty_message_falls_back_to_default(self):
        selector = _selector()
        assert selector.select("") is ModelProfile.SUPER

    def test_auto_is_case_insensitive(self):
        assert _selector().select("What is COMPLEX reasoning?") is ModelProfile.ULTRA

    def test_tie_lightning_vs_super_resolves_to_super(self):
        # "quick" matches LIGHTNING; "general" matches SUPER → tie → SUPER
        assert _selector().select("A quick general question") is ModelProfile.SUPER

    def test_tie_super_vs_ultra_resolves_to_super(self):
        # "complex" matches ULTRA; "task" matches SUPER → tie → SUPER
        assert _selector().select("Handle this complex task") is ModelProfile.SUPER

    def test_tie_lightning_vs_ultra_resolves_to_super(self):
        # "quick" matches LIGHTNING; "complex" matches ULTRA → tie → SUPER
        assert _selector().select("A quick complex overview") is ModelProfile.SUPER

    def test_tie_all_three_resolves_to_super(self):
        # "quick" (LIGHTNING), "task" (SUPER), "complex" (ULTRA) → all tie → SUPER
        assert _selector().select("A quick complex task") is ModelProfile.SUPER


# ===========================================================================
# ModelSelector: explicit selection
# ===========================================================================


class TestExplicitSelection:
    def test_explicit_lightning(self):
        assert _selector().select("anything", "lightning") is ModelProfile.LIGHTNING

    def test_explicit_super(self):
        assert _selector().select("anything", "super") is ModelProfile.SUPER

    def test_explicit_ultra(self):
        assert _selector().select("anything", "ultra") is ModelProfile.ULTRA

    def test_explicit_enum_bypasses_auto(self):
        selector = _selector()
        # Even though the message would route to ULTRA, explicit
        # selection of LIGHTNING must be respected.
        assert (
            selector.select("complex architecture", ModelProfile.LIGHTNING)
            is ModelProfile.LIGHTNING
        )

    def test_invalid_string_raises(self):
        with pytest.raises(InvalidModelProfileError):
            _selector().select("hello", "claude")


# ===========================================================================
# ModelSelector: custom default
# ===========================================================================


class TestSelectorDefaults:
    def test_auto_no_match_uses_default(self):
        selector = ModelSelector(
            profiles=_default_profiles(),
            default_profile=ModelProfile.ULTRA,
        )
        assert selector.select("hello") is ModelProfile.ULTRA


# ===========================================================================
# ProviderRegistry
# ===========================================================================


class _StubProvider(AIProvider):
    def __init__(self, name: str = "stub") -> None:
        self.name_val = name
        self.caps_val: frozenset[ProviderCapability] = frozenset()

    @property
    def name(self) -> str:
        return self.name_val

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return self.caps_val

    async def generate(self, request):  # noqa: ARG002
        raise NotImplementedError

    async def stream(self, request):  # noqa: ARG002
        raise NotImplementedError
        yield  # pragma: no cover

    async def health_check(self) -> bool:
        return True


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = _StubProvider("alpha")
        registry.register(provider)
        assert registry.get("alpha") is provider

    def test_register_duplicate_raises(self):
        registry = ProviderRegistry()
        registry.register(_StubProvider("dup"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_StubProvider("dup"))

    def test_get_missing_raises_not_found(self):
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get("ghost")

    def test_has_returns_false_for_missing(self):
        assert ProviderRegistry().has("nope") is False

    def test_names_returns_sorted(self):
        registry = ProviderRegistry()
        registry.register(_StubProvider("zebra"))
        registry.register(_StubProvider("apple"))
        assert registry.names() == ["apple", "zebra"]

    def test_health_check_all(self):
        registry = ProviderRegistry()
        provider = _StubProvider("ok")
        provider.healthy = True

        # Patch health_check to return True
        async def _ok():  # noqa: ANN202
            return True

        import types
        provider.health_check = _ok  # type: ignore[method-assign]

        registry.register(provider)
        import asyncio
        results = asyncio.run(registry.health_check_all())
        assert results["ok"] is True

    def test_health_check_handles_failing_provider(self):
        registry = ProviderRegistry()
        provider = _StubProvider("bad")

        async def _fail():  # noqa: ANN202
            raise RuntimeError("boom")

        provider.health_check = _fail  # type: ignore[method-assign]
        registry.register(provider)

        import asyncio
        results = asyncio.run(registry.health_check_all())
        assert results["bad"] is False


# ===========================================================================
# NVIDIA Configuration (Sprint 4 Phase 1)
# ===========================================================================


from packages.providers.nvidia.config import NvidiaSettings
from packages.providers.nvidia.provider import NvidiaProvider


class TestNvidiaSettings:
    def test_env_prefix_is_nvidia(self):
        """The settings class must use NVIDIA_ prefix so field names map
        to the environment variables defined in the project's .env file:
        NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_TIMEOUT_SECONDS,
        NVIDIA_MODEL_LIGHTNING, NVIDIA_MODEL_SUPER, NVIDIA_MODEL_ULTRA.
        """
        from packages.providers.nvidia.config import NvidiaSettings

        assert NvidiaSettings.model_config.get("env_prefix") == "NVIDIA_"

    def test_api_key_loaded_from_nvidia_env_var(self, tmp_path, monkeypatch):
        """Verify NVIDIA_API_KEY env var maps to api_key field."""
        dotenv = tmp_path / ".env"
        dotenv.write_text("NVIDIA_API_KEY=nvapi-from-env-file\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

        from packages.providers.nvidia.config import NvidiaSettings

        settings = NvidiaSettings(_env_file=str(dotenv))
        assert settings.api_key == "nvapi-from-env-file"
        assert settings.has_api_key is True

    def test_all_nvidia_env_vars_loaded_from_dotenv(self, tmp_path, monkeypatch):
        """Verify all six NVIDIA_* env vars are correctly mapped."""
        dotenv = tmp_path / ".env"
        dotenv.write_text(
            "NVIDIA_API_KEY=nvapi-test\n"
            "NVIDIA_BASE_URL=https://custom.nvidia.com/v1\n"
            "NVIDIA_TIMEOUT_SECONDS=90\n"
            "NVIDIA_MODEL_LIGHTNING=nemotron-lightning\n"
            "NVIDIA_MODEL_SUPER=nemotron-super\n"
            "NVIDIA_MODEL_ULTRA=nemotron-ultra\n"
        )
        monkeypatch.chdir(tmp_path)
        for var in (
            "NVIDIA_API_KEY",
            "NVIDIA_BASE_URL",
            "NVIDIA_TIMEOUT_SECONDS",
            "NVIDIA_MODEL_LIGHTNING",
            "NVIDIA_MODEL_SUPER",
            "NVIDIA_MODEL_ULTRA",
        ):
            monkeypatch.delenv(var, raising=False)

        from packages.providers.nvidia.config import NvidiaSettings

        settings = NvidiaSettings(_env_file=str(dotenv))
        assert settings.api_key == "nvapi-test"
        assert settings.base_url == "https://custom.nvidia.com/v1"
        assert settings.timeout_seconds == 90
        assert settings.model_for(ModelProfile.LIGHTNING) == "nemotron-lightning"
        assert settings.model_for(ModelProfile.SUPER) == "nemotron-super"
        assert settings.model_for(ModelProfile.ULTRA) == "nemotron-ultra"

    def test_default_base_url(self):
        settings = NvidiaSettings.for_testing()
        assert settings.base_url == "https://integrate.api.nvidia.com/v1"

    def test_default_timeout(self):
        settings = NvidiaSettings.for_testing()
        assert settings.timeout_seconds == 60

    def test_default_api_key_is_empty(self):
        settings = NvidiaSettings.for_testing()
        assert settings.api_key == ""
        assert settings.has_api_key is False

    def test_api_key_from_constructor(self):
        settings = NvidiaSettings.for_testing(api_key="sk-test-key")
        assert settings.api_key == "sk-test-key"
        assert settings.has_api_key is True

    def test_custom_base_url_from_constructor(self):
        settings = NvidiaSettings.for_testing(base_url="https://custom.example.com/v1")
        assert settings.base_url == "https://custom.example.com/v1"

    def test_custom_timeout_from_constructor(self):
        settings = NvidiaSettings.for_testing(timeout_seconds=120)
        assert settings.timeout_seconds == 120

    def test_model_mapping_lightning_from_constructor(self):
        settings = NvidiaSettings.for_testing(model_lightning="nemotron-3.5-lightning")
        assert settings.model_for(ModelProfile.LIGHTNING) == "nemotron-3.5-lightning"

    def test_model_mapping_super_from_constructor(self):
        settings = NvidiaSettings.for_testing(model_super="nemotron-3-super")
        assert settings.model_for(ModelProfile.SUPER) == "nemotron-3-super"

    def test_model_mapping_ultra_from_constructor(self):
        settings = NvidiaSettings.for_testing(model_ultra="nemotron-3-ultra")
        assert settings.model_for(ModelProfile.ULTRA) == "nemotron-3-ultra"

    def test_model_mapping_unset_returns_none(self):
        settings = NvidiaSettings.for_testing(
            model_lightning=None, model_super=None, model_ultra=None
        )
        assert settings.model_for(ModelProfile.LIGHTNING) is None
        assert settings.model_for(ModelProfile.SUPER) is None
        assert settings.model_for(ModelProfile.ULTRA) is None


class TestNvidiaProviderConfig:
    def test_auto_rejected_by_resolve_model(self):
        settings = NvidiaSettings(api_key="", model_lightning=None, model_super=None, model_ultra=None)
        provider = NvidiaProvider(settings=settings)
        with pytest.raises(InvalidModelProfileError):
            provider.resolve_model(ModelProfile.AUTO)

    def test_missing_model_raises_unavailable(self):
        settings = NvidiaSettings(api_key="", model_lightning=None, model_super=None, model_ultra=None)
        provider = NvidiaProvider(settings=settings)
        with pytest.raises(ProviderUnavailableError):
            provider.resolve_model(ModelProfile.LIGHTNING)

    def test_missing_model_message_contains_profile(self):
        settings = NvidiaSettings(api_key="", model_lightning=None, model_super=None, model_ultra=None)
        provider = NvidiaProvider(settings=settings)
        with pytest.raises(ProviderUnavailableError, match="lightning"):
            provider.resolve_model(ModelProfile.LIGHTNING)

    def test_configured_model_returns_id(self):
        settings = NvidiaSettings(
            api_key="sk-test",
            model_super="nemotron-3-super",
        )
        provider = NvidiaProvider(settings=settings)
        assert provider.resolve_model(ModelProfile.SUPER) == "nemotron-3-super"

    def test_health_check_returns_false(self):
        provider = NvidiaProvider(settings=NvidiaSettings(api_key=""))
        import asyncio

        assert asyncio.run(provider.health_check()) is False

    def test_stream_raises_not_implemented(self):
        import asyncio

        provider = NvidiaProvider(settings=NvidiaSettings(api_key=""))
        with pytest.raises(NotImplementedError):
            asyncio.run(provider.stream(None).__anext__())  # type: ignore[arg-type]


# ===========================================================================
# NVIDIA HTTP Client (Sprint 4 Phase 2)
# ===========================================================================


from packages.providers.nvidia.client import NvidiaHttpClient


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    @property
    def is_success(self) -> bool:
        return self.status_code < 400


class TestNvidiaHttpClient:
    @staticmethod
    def _client(api_key: str = "test-api-key") -> NvidiaHttpClient:
        from packages.providers.nvidia.config import NvidiaSettings

        settings = NvidiaSettings(
            api_key=api_key,
            base_url="https://test.nvidia.com/v1",
            timeout_seconds=30,
        )
        return NvidiaHttpClient(settings)

    def test_default_base_url(self):
        from packages.providers.nvidia.config import NvidiaSettings

        settings = NvidiaSettings.for_testing()
        client = NvidiaHttpClient(settings)
        assert client._settings.base_url == "https://integrate.api.nvidia.com/v1"

    def test_uses_configured_base_url(self):
        client = self._client()
        assert client._settings.base_url == "https://test.nvidia.com/v1"

    def test_authorization_header_with_api_key(self):
        client = self._client(api_key="my-secret-key")
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer my-secret-key"

    def test_no_auth_header_without_api_key(self):
        from packages.providers.nvidia.config import NvidiaSettings

        settings = NvidiaSettings.for_testing(api_key="")
        client = NvidiaHttpClient(settings)
        headers = client._build_headers()
        assert "Authorization" not in headers

    def test_api_key_not_in_error_messages(self):
        client = self._client(api_key="super-secret-key")
        exc = ProviderUnavailableError("NVIDIA API is unreachable")
        assert "super-secret-key" not in str(exc)

    def test_post_constructs_correct_url(self):
        client = self._client()

        async def _fake_post(url, **kwargs):
            assert url == "/chat/completions"
            assert kwargs["json"] == {"model": "test", "messages": []}
            return _FakeResponse(200)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _fake_post
        client._client.get = unittest.mock.AsyncMock()

        import asyncio

        result = asyncio.run(client.post("/chat/completions", json={"model": "test", "messages": []}))
        assert result.status_code == 200

    def test_post_adds_leading_slash(self):
        client = self._client()
        captured: list[str] = []

        async def _fake_post(url, **kwargs):
            captured.append(url)
            return _FakeResponse(200)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _fake_post

        import asyncio

        asyncio.run(client.post("chat/completions"))
        assert captured[0] == "/chat/completions"

    def test_configured_timeout(self):
        from packages.providers.nvidia.config import NvidiaSettings

        settings = NvidiaSettings(timeout_seconds=120)
        client = NvidiaHttpClient(settings)
        assert client._settings.timeout_seconds == 120

    def test_successful_response_returned(self):
        client = self._client()

        async def _fake_post(*args, **kwargs):
            return _FakeResponse(200)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _fake_post

        import asyncio

        result = asyncio.run(client.post("/chat/completions"))
        assert result.status_code == 200

    def test_connection_error_translated(self):
        client = self._client()

        async def _raise_connect(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _raise_connect

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="unreachable"):
            asyncio.run(client.post("/chat/completions"))

    def test_timeout_translated(self):
        client = self._client()

        async def _raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("timed out")

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _raise_timeout

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="timed out"):
            asyncio.run(client.post("/chat/completions"))

    def test_401_translated(self):
        client = self._client()

        async def _return_401(*args, **kwargs):
            return _FakeResponse(401)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _return_401

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="authentication"):
            asyncio.run(client.post("/chat/completions"))

    def test_403_translated(self):
        client = self._client()

        async def _return_403(*args, **kwargs):
            return _FakeResponse(403)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _return_403

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="authentication"):
            asyncio.run(client.post("/chat/completions"))

    def test_429_translated(self):
        client = self._client()

        async def _return_429(*args, **kwargs):
            return _FakeResponse(429)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _return_429

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="rate limit"):
            asyncio.run(client.post("/chat/completions"))

    def test_500_translated(self):
        client = self._client()

        async def _return_500(*args, **kwargs):
            return _FakeResponse(500)

        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = _return_500

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="server error"):
            asyncio.run(client.post("/chat/completions"))

    def test_no_real_network_calls(self):
        client = self._client()

        # If a real network call were attempted, httpx would attempt
        # DNS resolution. We verify the client uses a mock instead.
        import unittest.mock

        client._client = unittest.mock.AsyncMock()
        client._client.post = unittest.mock.AsyncMock(return_value=_FakeResponse(200))

        import asyncio

        result = asyncio.run(client.post("/chat/completions"))
        assert result.status_code == 200


# ===========================================================================
# NVIDIA Provider Generation (Sprint 4 Phase 3)
# ===========================================================================


from unittest.mock import AsyncMock, MagicMock, patch

from packages.providers.nvidia.config import NvidiaSettings
from packages.providers.nvidia.client import NvidiaHttpClient
from packages.providers.nvidia.provider import NvidiaProvider


_SAMPLE_RESPONSE = {
    "choices": [
        {
            "message": {"role": "assistant", "content": "Hello!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


def _make_provider(monkeypatch, api_key="test-api-key", model_super="nemotron-3-super"):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL_LIGHTNING", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL_SUPER", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL_ULTRA", raising=False)
    from packages.providers.nvidia.config import NvidiaSettings
    from packages.providers.nvidia.provider import NvidiaProvider
    settings = NvidiaSettings(
        api_key=api_key,
        model_lightning="nemotron-3.5-lightning",
        model_super=model_super,
        model_ultra="nemotron-3-ultra",
    )
    return NvidiaProvider(settings=settings)


class TestNvidiaProviderResolveModel:
    def test_resolves_lightning(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        assert provider.resolve_model(ModelProfile.LIGHTNING) == "nemotron-3.5-lightning"

    def test_resolves_super(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        assert provider.resolve_model(ModelProfile.SUPER) == "nemotron-3-super"

    def test_resolves_ultra(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        assert provider.resolve_model(ModelProfile.ULTRA) == "nemotron-3-ultra"

    def test_auto_rejected(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        with pytest.raises(InvalidModelProfileError):
            provider.resolve_model(ModelProfile.AUTO)

    def test_missing_model_raises_unavailable(self, monkeypatch):
        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        with pytest.raises(ProviderUnavailableError, match="super"):
            provider.resolve_model(ModelProfile.SUPER)


class TestNvidiaProviderGenerate:
    def _mock_client(self):
        mock_response = MagicMock()
        mock_response.json.return_value = _SAMPLE_RESPONSE
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.start = AsyncMock()
        return mock_client

    def _request(self, model="super"):
        return ProviderRequest(
            messages=[ProviderMessage(role="user", content="Hello")],
            model=model,
        )

    def test_generate_calls_client_with_correct_url(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            asyncio.run(provider.generate(self._request()))
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/chat/completions"

    def test_generate_includes_model_id_in_payload(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            asyncio.run(provider.generate(self._request()))
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["model"] == "nemotron-3-super"

    def test_generate_includes_messages(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        messages = [
            ProviderMessage(role="system", content="You are helpful."),
            ProviderMessage(role="user", content="Hello"),
        ]
        request = ProviderRequest(messages=messages, model="super")

        mock_response = MagicMock()
        mock_response.json.return_value = _SAMPLE_RESPONSE

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            asyncio.run(provider.generate(request))
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["messages"] == [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ]

    def test_generate_preserves_message_ordering(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        messages = [
            ProviderMessage(role="user", content="First"),
            ProviderMessage(role="assistant", content="Second"),
            ProviderMessage(role="user", content="Third"),
        ]
        request = ProviderRequest(messages=messages, model="super")

        mock_response = MagicMock()
        mock_response.json.return_value = _SAMPLE_RESPONSE

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            asyncio.run(provider.generate(request))
            payload = mock_client.post.call_args.kwargs["json"]
            assert [m["content"] for m in payload["messages"]] == [
                "First",
                "Second",
                "Third",
            ]

    def test_generate_does_not_mutate_request(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        request = ProviderRequest(
            messages=[ProviderMessage(role="user", content="Hello")],
            model="super",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = _SAMPLE_RESPONSE

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            asyncio.run(provider.generate(request))
            assert request.model == "super"
            assert request.messages[0].role == "user"

    def test_generate_produces_provider_response(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            result = asyncio.run(provider.generate(self._request()))
            assert isinstance(result, ProviderResponse)
            assert result.content == "Hello!"
            assert result.model == "nemotron-3-super"

    def test_generate_maps_usage(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            result = asyncio.run(provider.generate(self._request()))
            assert result.usage.input_tokens == 10
            assert result.usage.output_tokens == 5

    def test_generate_auto_model_raises_invalid(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        request = ProviderRequest(
            messages=[ProviderMessage(role="user", content="Hello")],
            model="auto",
        )
        with pytest.raises(InvalidModelProfileError, match="AUTO"):
            import asyncio

            asyncio.run(provider.generate(request))

    def test_generate_none_model_raises_invalid(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        request = ProviderRequest(
            messages=[ProviderMessage(role="user", content="Hello")],
            model=None,
        )
        with pytest.raises(InvalidModelProfileError, match="required"):
            import asyncio

            asyncio.run(provider.generate(request))

    def test_generate_unknown_model_raises_invalid(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        request = ProviderRequest(
            messages=[ProviderMessage(role="user", content="Hello")],
            model="nonexistent-model",
        )
        with pytest.raises(InvalidModelProfileError, match="nonexistent-model"):
            import asyncio

            asyncio.run(provider.generate(request))

    def test_generate_http_error_propagates(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ProviderUnavailableError("NVIDIA API server error (HTTP 500)"))
        mock_client.aclose = AsyncMock()
        mock_client.start = AsyncMock()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            with pytest.raises(ProviderUnavailableError):
                asyncio.run(provider.generate(self._request()))

    def test_no_api_key_in_exceptions(self, monkeypatch):
        provider = _make_provider(monkeypatch, api_key="super-secret-12345")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ProviderUnavailableError("some error"))
        mock_client.aclose = AsyncMock()
        mock_client.start = AsyncMock()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            with pytest.raises(ProviderUnavailableError) as exc_info:
                asyncio.run(provider.generate(self._request()))
            assert "super-secret-12345" not in str(exc_info.value)

    def test_generate_no_real_network_calls(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            result = asyncio.run(provider.generate(self._request()))
            assert result.content == "Hello!"

    def test_injected_client_skips_start_and_close(self, monkeypatch):
        """When a client is injected, the provider must not manage its lifecycle."""
        provider = _make_provider(monkeypatch)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(json=lambda: _SAMPLE_RESPONSE))
        # aclose is NOT mocked on purpose — we verify it is NOT called

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient",
            return_value=mock_client,
        ):
            pass  # we set _http_client directly

        provider._http_client = mock_client

        import asyncio

        asyncio.run(provider.generate(self._request()))
        mock_client.start.assert_not_called()
        mock_client.aclose.assert_not_called()

    def test_generate_with_temperature(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            request = ProviderRequest(
                messages=[ProviderMessage(role="user", content="Hello")],
                model="super",
                temperature=0.7,
            )
            asyncio.run(provider.generate(request))
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["temperature"] == 0.7

    def test_generate_lightning_model(self, monkeypatch):
        provider = _make_provider(monkeypatch)
        mock_client = self._mock_client()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            request = ProviderRequest(
                messages=[ProviderMessage(role="user", content="Hello")],
                model="lightning",
            )
            asyncio.run(provider.generate(request))
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["model"] == "nemotron-3.5-lightning"


class TestNvidiaProviderBehavior:
    def test_stream_raises_not_implemented(self):
        provider = NvidiaProvider(settings=NvidiaSettings.for_testing())
        import asyncio

        with pytest.raises(NotImplementedError):
            asyncio.run(provider.stream(None).__anext__())  # type: ignore[arg-type]

    def test_health_check_returns_false(self):
        provider = NvidiaProvider(settings=NvidiaSettings.for_testing())
        import asyncio

        assert asyncio.run(provider.health_check()) is False

    def test_generate_no_longer_raises_not_implemented(self, monkeypatch):
        from unittest.mock import AsyncMock, MagicMock, patch

        provider = _make_provider(monkeypatch)
        mock_response = MagicMock()
        mock_response.json.return_value = _SAMPLE_RESPONSE
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.start = AsyncMock()

        with patch(
            "packages.providers.nvidia.provider.NvidiaHttpClient"
        ) as mock_cls:
            mock_cls.return_value = mock_client
            import asyncio

            result = asyncio.run(
                provider.generate(
                    ProviderRequest(
                        messages=[ProviderMessage(role="user", content="Hi")],
                        model="super",
                    )
                )
            )
            assert isinstance(result, ProviderResponse)


# ===========================================================================
# Malformed response parsing (Sprint 4 Phase 3.1 — Issue 3)
# ===========================================================================


class TestParseResponseMalformed:
    """_parse_response must handle every malformed field safely."""

    @pytest.fixture
    def provider(self):
        settings = NvidiaSettings.for_testing(api_key="test")
        return NvidiaProvider(settings=settings)

    def test_non_dict_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="unexpected response format"):
            provider._parse_response("not a dict", "model-1")  # type: ignore[arg-type]

    def test_missing_choices_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="missing 'choices'"):
            provider._parse_response({"usage": {}}, "model-1")

    def test_empty_choices_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="empty response"):
            provider._parse_response({"choices": []}, "model-1")

    def test_choices_not_list_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="unexpected response format"):
            provider._parse_response({"choices": "bad"}, "model-1")

    def test_malformed_choice_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="malformed choice"):
            provider._parse_response({"choices": ["not-a-dict"]}, "model-1")

    def test_missing_message_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="missing 'message'"):
            provider._parse_response({"choices": [{"finish_reason": "stop"}]}, "model-1")

    def test_malformed_message_raises(self, provider):
        with pytest.raises(ProviderUnavailableError, match="malformed message"):
            provider._parse_response(
                {"choices": [{"message": "not-a-dict"}]}, "model-1"
            )

    def test_null_content_becomes_empty(self, provider):
        result = provider._parse_response(
            {"choices": [{"message": {"content": None}}]}, "model-1"
        )
        assert result.content == ""

    def test_missing_content_defaults_empty(self, provider):
        result = provider._parse_response(
            {"choices": [{"message": {}}]}, "model-1"
        )
        assert result.content == ""

    def test_missing_usage_defaults_zero(self, provider):
        result = provider._parse_response(
            {"choices": [{"message": {"content": "hi"}}]}, "model-1"
        )
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0

    def test_null_usage_defaults_zero(self, provider):
        result = provider._parse_response(
            {"choices": [{"message": {"content": "hi"}}], "usage": None}, "model-1"
        )
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0

    def test_non_dict_usage_defaults_zero(self, provider):
        result = provider._parse_response(
            {"choices": [{"message": {"content": "hi"}}], "usage": "bad"}, "model-1"
        )
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0

    def test_missing_token_counts_default_zero(self, provider):
        result = provider._parse_response(
            {"choices": [{"message": {"content": "hi"}}], "usage": {}}, "model-1"
        )
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0

    def test_valid_response_parses(self, provider):
        result = provider._parse_response(
            {
                "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
            "model-1",
        )
        assert result.content == "Hello"
        assert result.finish_reason == "stop"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5


# ===========================================================================
# Fail-fast API key (Sprint 4 Phase 3.1 — Issue 4)
# ===========================================================================


class TestFailFastNoApiKey:
    """No network call occurs when NVIDIA_API_KEY is missing."""

    def test_post_raises_before_network_when_no_api_key(self):
        settings = NvidiaSettings.for_testing(api_key="")
        client = NvidiaHttpClient(settings)
        from unittest.mock import AsyncMock

        client._client = AsyncMock()

        import asyncio

        with pytest.raises(ProviderUnavailableError, match="NVIDIA_API_KEY is not configured"):
            asyncio.run(client.post("/chat/completions"))

        # The mock was never called — no network request.
        client._client.post.assert_not_called()

    def test_has_api_key_false_prevents_request(self):
        settings = NvidiaSettings.for_testing()
        assert settings.has_api_key is False
        client = NvidiaHttpClient(settings)
        assert not client._settings.has_api_key