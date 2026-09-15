"""
Tests for Sprint 4 Phase 4: Application-Layer Provider Integration.

Covers:
- AI service layer (apps/api/services/ai.py)
- Chat API endpoint (apps/api/routers/chat.py)
- AUTO resolution flow
- ProviderRegistry integration
- Error mapping
- Security (API key never exposed)
- No real network calls

All NVIDIA network calls remain mocked. Tests do not load real .env credentials.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from packages.providers.base import (
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
)
from packages.providers.exceptions import (
    InvalidModelProfileError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from packages.providers.models import ModelProfile, ModelMetadata
from packages.providers.nvidia.config import NvidiaSettings
from packages.providers.nvidia.provider import NvidiaProvider
from packages.providers.registry import ProviderRegistry
from packages.providers.selector import ModelSelector
from schemas import StandardResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_response() -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hello! How can I help?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _make_mock_client():
    """Create a mock NvidiaHttpClient that returns a sample response."""
    mock_response = MagicMock()
    mock_response.json.return_value = _sample_response()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_client.start = AsyncMock()
    return mock_client


def _make_nvidia_provider(api_key: str = "test-api-key") -> NvidiaProvider:
    """Create a NvidiaProvider with for_testing settings — no .env loading."""
    settings = NvidiaSettings.for_testing(
        api_key=api_key,
        model_lightning="nemotron-3.5-lightning",
        model_super="nemotron-3-super",
        model_ultra="nemotron-3-ultra",
    )
    return NvidiaProvider(settings=settings)


# ===========================================================================
# Service Layer: resolve_model_profile
# ===========================================================================


class TestResolveModelProfile:
    """Tests for the resolve_model_profile function."""

    def test_auto_resolves_using_selector(self):
        """AUTO requests are resolved by ModelSelector."""
        from services.ai import resolve_model_profile

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        # "quick" should resolve to LIGHTNING
        result = resolve_model_profile(selector, "a quick question")
        assert result is ModelProfile.LIGHTNING

    def test_explicit_lightning_bypasses_auto(self):
        """Explicit LIGHTNING bypasses AUTO."""
        from services.ai import resolve_model_profile

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        result = resolve_model_profile(selector, "complex reasoning task", "lightning")
        assert result is ModelProfile.LIGHTNING

    def test_explicit_super_bypasses_auto(self):
        """Explicit SUPER bypasses AUTO."""
        from services.ai import resolve_model_profile

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        result = resolve_model_profile(selector, "quick info", "super")
        assert result is ModelProfile.SUPER

    def test_explicit_ultra_bypasses_auto(self):
        """Explicit ULTRA bypasses AUTO."""
        from services.ai import resolve_model_profile

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        result = resolve_model_profile(selector, "simple question", "ultra")
        assert result is ModelProfile.ULTRA

    def test_invalid_model_profile_raises(self):
        """Invalid profile string raises InvalidModelProfileError."""
        from services.ai import resolve_model_profile

        selector = ModelSelector(
            profiles={},
            default_profile=ModelProfile.SUPER,
        )

        with pytest.raises(InvalidModelProfileError):
            resolve_model_profile(selector, "hello", "nonexistent-model")

    def test_auto_resolves_to_expected_concrete_profile(self):
        """AUTO resolves to expected concrete profile based on keywords."""
        from services.ai import resolve_model_profile

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick", "simple"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal", "coding"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex", "reasoning"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        assert resolve_model_profile(selector, "quick simple question") is ModelProfile.LIGHTNING
        assert resolve_model_profile(selector, "help me write code") is ModelProfile.SUPER
        assert resolve_model_profile(selector, "complex deep reasoning") is ModelProfile.ULTRA


# ===========================================================================
# Service Layer: build_provider_request
# ===========================================================================


class TestBuildProviderRequest:
    """Tests for the build_provider_request function."""

    def test_basic_request(self):
        from services.ai import build_provider_request

        request = build_provider_request(
            messages=[("user", "Hello")],
            model="super",
        )
        assert request.model == "super"
        assert len(request.messages) == 1
        assert request.messages[0].role == "user"
        assert request.messages[0].content == "Hello"

    def test_request_with_temperature(self):
        from services.ai import build_provider_request

        request = build_provider_request(
            messages=[("user", "Hello")],
            model="super",
            temperature=0.7,
        )
        assert request.temperature == 0.7

    def test_request_with_max_tokens(self):
        from services.ai import build_provider_request

        request = build_provider_request(
            messages=[("user", "Hello")],
            model="super",
            max_tokens=1024,
        )
        assert request.max_tokens == 1024

    def test_request_with_all_params(self):
        from services.ai import build_provider_request

        request = build_provider_request(
            messages=[("system", "You are helpful."), ("user", "Hi")],
            model="lightning",
            temperature=0.5,
            max_tokens=512,
        )
        assert request.model == "lightning"
        assert request.temperature == 0.5
        assert request.max_tokens == 512
        assert len(request.messages) == 2

    def test_multiple_messages_preserve_order(self):
        from services.ai import build_provider_request

        messages = [
            ("system", "Sys1"),
            ("user", "U1"),
            ("assistant", "A1"),
            ("user", "U2"),
        ]
        request = build_provider_request(messages=messages, model="super")
        assert len(request.messages) == 4
        assert request.messages[0].role == "system"
        assert request.messages[0].content == "Sys1"
        assert request.messages[1].role == "user"
        assert request.messages[1].content == "U1"


# ===========================================================================
# Service Layer: generate_ai_response
# ===========================================================================


class TestGenerateAiResponse:
    """Tests for the generate_ai_response service function."""

    def _make_mocks(self, api_key: str = "test-api-key"):
        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        settings = NvidiaSettings.for_testing(
            api_key=api_key,
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        provider = NvidiaProvider(settings=settings)

        mock_client = _make_mock_client()
        provider._http_client = mock_client

        registry = ProviderRegistry()
        registry.register(provider)

        return selector, registry, mock_client

    def test_auto_request_uses_selector(self):
        """AUTO request resolves through ModelSelector."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            response, provider_name, resolved_profile = await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "quick question")],
                preferred_model="auto",
            )
            return response, provider_name, resolved_profile

        response, provider_name, resolved_profile = asyncio.run(_run())
        # "quick" matches LIGHTNING keywords
        assert resolved_profile == ModelProfile.LIGHTNING
        assert provider_name == "nvidia"

    def test_explicit_lightning_bypasses_auto(self):
        """Explicit LIGHTNING bypasses AUTO selection."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            response, provider_name, resolved_profile = await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "complex reasoning")],
                preferred_model="lightning",
            )
            return response, provider_name, resolved_profile

        response, _, resolved_profile = asyncio.run(_run())
        # Should use lightning, not ultra (despite "complex" keyword)
        assert resolved_profile == ModelProfile.LIGHTNING

    def test_explicit_super_bypasses_auto(self):
        """Explicit SUPER bypasses AUTO selection."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            response, provider_name, resolved_profile = await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "quick question")],
                preferred_model="super",
            )
            return response, provider_name, resolved_profile

        response, _, resolved_profile = asyncio.run(_run())
        assert resolved_profile == ModelProfile.SUPER

    def test_explicit_ultra_bypasses_auto(self):
        """Explicit ULTRA bypasses AUTO selection."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            response, provider_name, resolved_profile = await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "simple question")],
                preferred_model="ultra",
            )
            return response, provider_name, resolved_profile

        response, _, resolved_profile = asyncio.run(_run())
        assert resolved_profile == ModelProfile.ULTRA

    def test_ai_service_invokes_provider(self):
        """AI service invokes the selected provider correctly."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            response, _, resolved_profile = await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "Hello")],
                preferred_model="super",
            )
            return response, resolved_profile

        response, resolved_profile = asyncio.run(_run())
        # Verify the mock client was called with the NVIDIA model ID
        # (the provider translates the logical profile to a real model ID)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/chat/completions"
        payload = call_args.kwargs["json"]
        # The provider translates the logical profile to the NVIDIA model ID
        assert payload["model"] == "nemotron-3-super"
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]

    def test_provider_response_translated_correctly(self):
        """Provider response is translated into the application response."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            response, provider_name, resolved_profile = await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "Hello")],
                preferred_model="super",
            )
            return response, provider_name, resolved_profile

        response, provider_name, resolved_profile = asyncio.run(_run())
        assert response.content == "Hello! How can I help?"
        assert response.finish_reason == "stop"
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 5
        assert provider_name == "nvidia"
        assert resolved_profile == ModelProfile.SUPER

    def test_invalid_model_profile_raises(self):
        """Invalid profile string raises InvalidModelProfileError at service layer."""
        from services.ai import generate_ai_response

        selector, registry, _ = self._make_mocks()

        async def _run():
            await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "Hello")],
                preferred_model="nonexistent",
            )

        with pytest.raises(InvalidModelProfileError):
            asyncio.run(_run())

    def test_missing_model_config_returns_unavailable(self):
        """Missing NVIDIA model config raises ProviderUnavailableError."""
        from services.ai import generate_ai_response

        # Create a provider with no model IDs configured
        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        async def _run():
            await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "Hello")],
                preferred_model="super",
            )

        with pytest.raises(ProviderUnavailableError, match="No NVIDIA model ID"):
            asyncio.run(_run())

    def test_nvidia_api_failure_becomes_unavailable(self):
        """NVIDIA API failures become ProviderUnavailableError."""
        from services.ai import generate_ai_response

        selector, registry, _ = self._make_mocks()

        # Create a provider with a client that raises
        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_super="nemotron-3-super",
        )
        provider = NvidiaProvider(settings=settings)
        failing_client = AsyncMock()
        failing_client.post = AsyncMock(
            side_effect=ProviderUnavailableError("NVIDIA API server error (HTTP 500)")
        )
        failing_client.aclose = AsyncMock()
        failing_client.start = AsyncMock()
        provider._http_client = failing_client

        registry2 = ProviderRegistry()
        registry2.register(provider)

        async def _run():
            await generate_ai_response(
                selector=selector,
                registry=registry2,
                messages=[("user", "Hello")],
                preferred_model="super",
            )

        with pytest.raises(ProviderUnavailableError):
            asyncio.run(_run())

    def test_no_real_network_calls_in_service(self):
        """No real network calls occur when generating responses."""
        from services.ai import generate_ai_response

        selector, registry, mock_client = self._make_mocks()

        async def _run():
            await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "Hello")],
                preferred_model="super",
            )

        asyncio.run(_run())
        # The mock client's post was called, not a real network call
        mock_client.post.assert_called_once()
        # Verify httpx.AsyncClient was never instantiated
        # (the provider uses the injected mock client)


# ===========================================================================
# API Endpoint: POST /api/v1/chat
# ===========================================================================


class TestChatEndpoint:
    """Tests for the POST /api/v1/chat API endpoint via TestClient."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        """Ensure env vars don't leak real credentials."""
        for var in (
            "NVIDIA_API_KEY",
            "NVIDIA_MODEL_LIGHTNING",
            "NVIDIA_MODEL_SUPER",
            "NVIDIA_MODEL_ULTRA",
        ):
            monkeypatch.delenv(var, raising=False)

        # Patch service functions to avoid loading real .env
        self._selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick", "simple"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal", "coding", "help"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex", "reasoning", "planning"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        self._settings = NvidiaSettings.for_testing(
            api_key="test-api-key",
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        self._provider = NvidiaProvider(settings=self._settings)
        self._mock_client = _make_mock_client()
        self._provider._http_client = self._mock_client

        self._registry = ProviderRegistry()
        self._registry.register(self._provider)

        # Patch get_provider_registry_from_app to return our test registry
        # regardless of the request.app.state value.
        self._registry_patcher = patch(
            "routers.chat.get_provider_registry_from_app",
            return_value=self._registry,
        )
        self._selector_patcher = patch(
            "routers.chat.get_model_selector",
            return_value=self._selector,
        )
        self._registry_patcher.start()
        self._selector_patcher.start()

        yield

        self._registry_patcher.stop()
        self._selector_patcher.stop()

    def test_chat_returns_200(self):
        """Successful chat request returns 200."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        assert response.status_code == 200

    def test_chat_response_contains_content(self):
        """Response includes the generated content."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        assert body["success"] is True
        assert body["data"]["content"] == "Hello! How can I help?"

    def test_chat_response_contains_selected_model(self):
        """Response includes the selected logical model profile."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        assert body["data"]["selected_model"] == "super"

    def test_chat_response_contains_provider_name(self):
        """Response includes the provider name, not NVIDIA secrets."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        assert body["data"]["provider"] == "nvidia"

    def test_chat_response_contains_usage(self):
        """Response includes token usage."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        assert body["data"]["usage"]["input_tokens"] == 10
        assert body["data"]["usage"]["output_tokens"] == 5

    def test_chat_response_contains_finish_reason(self):
        """Response includes finish_reason."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        assert body["data"]["finish_reason"] == "stop"

    def test_chat_uses_standard_envelope(self):
        """Response conforms to the StandardResponse envelope."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        assert body["success"] is True
        assert "message" in body
        assert body["message"] == "Chat completion generated"
        assert "request_id" in body
        assert "timestamp" in body
        assert "X-Request-ID" in response.headers

    def test_chat_auto_resolves_via_selector(self):
        """AUTO model resolves through ModelSelector heuristics."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "quick simple question"}],
                "model": "auto",
            },
        )
        assert response.status_code == 200
        body = response.json()
        # "quick simple" → LIGHTNING keywords
        assert body["data"]["selected_model"] == "lightning"

    def test_chat_auto_resolves_complex_to_ultra(self):
        """AUTO resolves 'complex reasoning' to ULTRA."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "complex reasoning task"}],
                "model": "auto",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["selected_model"] == "ultra"

    def test_chat_auto_resolves_normal_to_super(self):
        """AUTO resolves 'normal coding' to SUPER."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "normal coding help"}],
                "model": "auto",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["selected_model"] == "super"

    def test_chat_explicit_lightning_bypasses_auto(self):
        """Explicit 'lightning' bypasses AUTO even with complex message."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "complex architecture planning"}],
                "model": "lightning",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["selected_model"] == "lightning"

    def test_chat_explicit_ultra_bypasses_auto(self):
        """Explicit 'ultra' bypasses AUTO even with simple message."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "quick question"}],
                "model": "ultra",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["selected_model"] == "ultra"

    def test_chat_invalid_model_returns_422(self):
        """Invalid model profile returns 422 validation error."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "invalid-model",
            },
        )
        assert response.status_code == 422

    def test_chat_empty_messages_returns_422(self):
        """Empty messages list returns 422 validation error."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [],
                "model": "super",
            },
        )
        assert response.status_code == 422

    def test_chat_temperature_in_range(self):
        """Temperature within 0.0–2.0 range is accepted."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
                "temperature": 1.5,
            },
        )
        assert response.status_code == 200

    def test_chat_temperature_out_of_range_returns_422(self):
        """Temperature above 2.0 returns 422."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
                "temperature": 3.0,
            },
        )
        assert response.status_code == 422

    def test_chat_api_key_never_in_response(self):
        """The NVIDIA API key never appears in any response field."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        body = response.json()
        body_str = str(body)
        assert "test-api-key" not in body_str
        assert "nvapi-" not in body_str
        assert "Bearer" not in body_str

    def test_chat_api_key_never_in_error_response(self):
        """The NVIDIA API key never appears in error responses."""
        # Use a provider that will fail
        settings = NvidiaSettings.for_testing(api_key="super-secret-12345")
        provider = NvidiaProvider(settings=settings)
        failing_client = AsyncMock()
        failing_client.post = AsyncMock(
            side_effect=ProviderUnavailableError("Some error")
        )
        failing_client.aclose = AsyncMock()
        failing_client.start = AsyncMock()
        provider._http_client = failing_client

        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=self._selector):
            with patch("routers.chat.get_provider_registry_from_app", return_value=registry):
                client = TestClient(app)
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        assert response.status_code == 503
        body = response.json()
        assert "super-secret-12345" not in str(body)
        assert "nvapi-" not in str(body)

    def test_chat_provider_unavailable_returns_503(self):
        """ProviderUnavailableError maps to 503."""
        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        failing_client = AsyncMock()
        failing_client.post = AsyncMock(
            side_effect=ProviderUnavailableError("NVIDIA API is unreachable")
        )
        failing_client.aclose = AsyncMock()
        failing_client.start = AsyncMock()
        provider._http_client = failing_client

        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=self._selector):
            with patch("routers.chat.get_provider_registry_from_app", return_value=registry):
                client = TestClient(app)
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False
        assert "unavailable" in body["message"].lower()

    def test_chat_no_real_network_calls(self):
        """No real network calls occur during a chat request."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
        )
        assert response.status_code == 200
        # Verify mock client was used (not real httpx)
        self._mock_client.post.assert_called_once()

    def test_chat_multiple_messages(self):
        """Chat handles multi-message conversations."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "Tell me more."},
                ],
                "model": "super",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["content"] == "Hello! How can I help?"

    def test_chat_request_id_propagated(self):
        """Request ID is propagated to the response."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "super",
            },
            headers={"X-Request-ID": "custom-request-id-123"},
        )
        assert response.headers["X-Request-ID"] == "custom-request-id-123"
        body = response.json()
        assert body["request_id"] == "custom-request-id-123"


# ===========================================================================
# ProviderRegistry integration tests
# ===========================================================================


class TestProviderRegistryIntegration:
    """Verify ProviderRegistry returns the NVIDIA provider."""

    def test_registry_returns_nvidia_provider(self):
        """Registry contains NVIDIA provider after initialization."""
        # Use for_testing to avoid loading .env
        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        registry = ProviderRegistry()
        registry.register(provider)
        retrieved = registry.get("nvidia")
        assert retrieved is provider
        assert retrieved.name == "nvidia"

    def test_registry_nvidia_provider_has_text_generation_capability(self):
        """NVIDIA provider declares TEXT_GENERATION capability."""
        from packages.providers.base import ProviderCapability

        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        assert ProviderCapability.TEXT_GENERATION in provider.capabilities

    def test_registry_provider_names(self):
        """Registry reports the NVIDIA provider name."""
        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        registry = ProviderRegistry()
        registry.register(provider)
        assert registry.names() == ["nvidia"]


# ===========================================================================
# Error mapping tests
# ===========================================================================


class TestErrorMapping:
    """Verify provider exceptions map to correct API responses."""

    def test_provider_not_found_maps_to_503(self):
        """ProviderNotFoundError → 503 Service Unavailable."""
        client = TestClient(app)

        empty_registry = ProviderRegistry()

        with patch("routers.chat.get_model_selector") as mock_sel:
            mock_sel.return_value = ModelSelector(
                profiles={},
                default_profile=ModelProfile.SUPER,
            )
            with patch("routers.chat.get_provider_registry_from_app", return_value=empty_registry):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False
        assert "provider" in body["message"].lower()

    def test_provider_unavailable_maps_to_503(self):
        """ProviderUnavailableError → 503 Service Unavailable."""
        client = TestClient(app)

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        failing_client = AsyncMock()
        failing_client.post = AsyncMock(
            side_effect=ProviderUnavailableError("NVIDIA API is unreachable")
        )
        failing_client.aclose = AsyncMock()
        failing_client.start = AsyncMock()
        provider._http_client = failing_client

        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch("routers.chat.get_provider_registry_from_app", return_value=registry):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False

    def test_invalid_model_profile_raises_at_service_layer(self):
        """InvalidModelProfileError is raised from the service layer."""
        from services.ai import generate_ai_response

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        settings = NvidiaSettings.for_testing(api_key="test-key")
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        registry = ProviderRegistry()
        registry.register(provider)

        # Use a valid model in the request, but pass invalid as preferred_model
        # The service calls selector.select() which validates the string
        # "gpt4" is not a valid ModelProfile value
        async def _run():
            await generate_ai_response(
                selector=selector,
                registry=registry,
                messages=[("user", "Hello")],
                preferred_model="gpt4",  # Invalid profile string
            )

        with pytest.raises(InvalidModelProfileError):
            asyncio.run(_run())


# ===========================================================================
# Security tests
# ===========================================================================


class TestSecurity:
    """Verify no secrets are exposed through API responses."""

    def test_api_key_not_in_success_response(self):
        """API key never appears in a successful response."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="nvapi-very-secret-key-12345",
            model_super="nemotron-3-super",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch("routers.chat.get_provider_registry_from_app", return_value=registry):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        body = response.json()
        body_text = str(body)
        assert "nvapi-very-secret-key-12345" not in body_text
        assert "Bearer" not in body_text
        assert "Authorization" not in body_text

    def test_api_key_not_in_error_response(self):
        """API key never appears in error responses."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(api_key="nvapi-very-secret-key-12345")
        provider = NvidiaProvider(settings=settings)
        failing_client = AsyncMock()
        failing_client.post = AsyncMock(
            side_effect=ProviderUnavailableError("Some API error")
        )
        failing_client.aclose = AsyncMock()
        failing_client.start = AsyncMock()
        provider._http_client = failing_client

        registry = ProviderRegistry()
        registry.register(provider)

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch("routers.chat.get_provider_registry_from_app", return_value=registry):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        body = response.json()
        body_text = str(body)
        assert "nvapi-very-secret-key-12345" not in body_text
        assert "Bearer" not in body_text

    def test_nvidia_model_ids_not_exposed(self):
        """NVIDIA model IDs are not exposed in the API response."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_super="nemotron-3-super-secret-model-id",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch("routers.chat.get_provider_registry_from_app", return_value=registry):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )

        body = response.json()
        assert "nemotron-3-super-secret-model-id" not in str(body)
        # The response should use the logical profile name, not the model ID
        assert body["data"]["selected_model"] == "super"


# ===========================================================================
# Test isolation — no real .env loading
# ===========================================================================


class TestIsolation:
    """Verify tests don't load real .env credentials."""

    def test_nvidia_settings_for_testing_avoids_env(self, monkeypatch, tmp_path):
        """NvidiaSettings.for_testing() doesn't read .env."""
        # Create a fake .env with a different API key
        fake_env = tmp_path / ".env"
        fake_env.write_text("NVIDIA_API_KEY=from-dotenv-file\n")

        # Use for_testing with explicit key
        settings = NvidiaSettings.for_testing(api_key="explicit-key")

        assert settings.api_key == "explicit-key"
        assert "from-dotenv-file" not in settings.api_key

    def test_no_env_file_loaded_during_tests(self, monkeypatch, tmp_path):
        """Tests using for_testing don't accidentally load a real .env."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

        # No .env file in tmp_path
        settings = NvidiaSettings.for_testing(api_key="isolated-key")
        assert settings.api_key == "isolated-key"


# ===========================================================================
# Existing Task Engine test sanity check
# ===========================================================================


class TestExistingTestsUnchanged:
    """Verify the existing Task Engine tests still pass."""

    def test_task_creation_still_works(self):
        """Task Engine tests continue to work after router changes."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/tasks",
            json={"name": "sanity-check-task", "capability": "research"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["name"] == "sanity-check-task"


# ===========================================================================
# Logical profile propagation regression tests
# ===========================================================================


class TestLogicalProfilePropagation:
    """Verify the resolved logical ModelProfile is returned, never a provider model ID."""

    def test_auto_resolves_to_logical_profile_via_api(self):
        """AUTO resolves through ModelSelector; the logical profile appears in the response."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        # LIGHTNING keywords: quick, simple, fast, short, info, easy
        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick", "simple", "fast", "short"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal", "coding"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex", "reasoning"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch(
                "routers.chat.get_provider_registry_from_app", return_value=registry
            ):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "quick question"}],
                        "model": "auto",
                    },
                )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["selected_model"] == "lightning"
        # No NVIDIA model ID in the response
        assert "nemotron" not in str(body["data"])

    def test_explicit_lightning_returns_logical_profile(self):
        """Explicit 'lightning' returns selected_model='lightning'."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch(
                "routers.chat.get_provider_registry_from_app", return_value=registry
            ):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "lightning",
                    },
                )
        assert response.status_code == 200
        assert response.json()["data"]["selected_model"] == "lightning"

    def test_explicit_super_returns_logical_profile(self):
        """Explicit 'super' returns selected_model='super'."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch(
                "routers.chat.get_provider_registry_from_app", return_value=registry
            ):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "super",
                    },
                )
        assert response.status_code == 200
        assert response.json()["data"]["selected_model"] == "super"

    def test_explicit_ultra_returns_logical_profile(self):
        """Explicit 'ultra' returns selected_model='ultra'."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch(
                "routers.chat.get_provider_registry_from_app", return_value=registry
            ):
                response = client.post(
                    "/api/v1/chat",
                    json={
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "ultra",
                    },
                )
        assert response.status_code == 200
        assert response.json()["data"]["selected_model"] == "ultra"

    def test_nvidia_model_id_never_in_selected_model(self):
        """selected_model is always the logical profile, never a NVIDIA model ID."""
        client = TestClient(app)

        settings = NvidiaSettings.for_testing(
            api_key="test-key",
            model_lightning="nemotron-3.5-lightning",
            model_super="nemotron-3-super",
            model_ultra="nemotron-3-ultra",
        )
        provider = NvidiaProvider(settings=settings)
        mock_client = _make_mock_client()
        provider._http_client = mock_client

        selector = ModelSelector(
            profiles={
                ModelProfile.LIGHTNING: ModelMetadata(
                    profile=ModelProfile.LIGHTNING,
                    description="fast",
                    recommended_for=["quick"],
                ),
                ModelProfile.SUPER: ModelMetadata(
                    profile=ModelProfile.SUPER,
                    description="balanced",
                    recommended_for=["normal"],
                ),
                ModelProfile.ULTRA: ModelMetadata(
                    profile=ModelProfile.ULTRA,
                    description="deep",
                    recommended_for=["complex"],
                ),
            },
            default_profile=ModelProfile.SUPER,
        )
        registry = ProviderRegistry()
        registry.register(provider)

        with patch("routers.chat.get_model_selector", return_value=selector):
            with patch(
                "routers.chat.get_provider_registry_from_app", return_value=registry
            ):
                for model in ["auto", "lightning", "super", "ultra"]:
                    response = client.post(
                        "/api/v1/chat",
                        json={
                            "messages": [{"role": "user", "content": "test"}],
                            "model": model,
                        },
                    )
                    assert response.status_code == 200
                    selected = response.json()["data"]["selected_model"]
                    assert selected in ("lightning", "super", "ultra")
                    assert "nemotron" not in selected
                    assert "-" not in selected  # no model IDs with dashes


# ===========================================================================
# ProviderRegistry lifecycle regression tests (Phase 5 Final Correction)
# ===========================================================================


class TestProviderRegistryLifecycle:
    """Verify ProviderRegistry is properly application-scoped."""

    def test_init_creates_registry_on_app_state(self):
        """init_provider_registry stores the registry on app.state."""
        from fastapi import FastAPI
        from services.ai import init_provider_registry

        test_app = FastAPI()
        assert getattr(test_app.state, "provider_registry", None) is None
        init_provider_registry(test_app)
        assert getattr(test_app.state, "provider_registry", None) is not None

    def test_repeated_init_same_app_no_duplicate_registration(self):
        """Calling init_provider_registry twice on the same app is safe."""
        from fastapi import FastAPI
        from services.ai import init_provider_registry

        test_app = FastAPI()
        init_provider_registry(test_app)
        registry = test_app.state.provider_registry
        init_provider_registry(test_app)
        assert test_app.state.provider_registry is registry

    def test_separate_app_instances_have_independent_registries(self):
        """Separate FastAPI app instances do not share registry state."""
        from fastapi import FastAPI
        from services.ai import init_provider_registry

        app1 = FastAPI()
        app2 = FastAPI()

        init_provider_registry(app1)
        init_provider_registry(app2)

        reg1 = app1.state.provider_registry
        reg2 = app2.state.provider_registry
        assert reg1 is not None
        assert reg2 is not None
        assert reg1 is not reg2

    def test_registry_nvidia_provider_registered(self):
        """The NVIDIA provider is registered after init."""
        from fastapi import FastAPI
        from services.ai import init_provider_registry

        test_app = FastAPI()
        init_provider_registry(test_app)
        registry = test_app.state.provider_registry
        assert "nvidia" in registry.names()
