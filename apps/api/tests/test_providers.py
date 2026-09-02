"""Tests for the Sprint 3 provider layer (model profiles, selector, registry).

Mirrors the package-level testing pattern established by the Task Engine:
pure domain tests against `packages.providers` directly, with no
FastAPI dependency. Each test exercises a single, named behavior so
that the README's "testing strategy" section stays accurate.

No API keys, network access, or external services are required.
"""

from __future__ import annotations

import pytest

from packages.providers.base import AIProvider, ProviderCapability
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
    def test_default_base_url(self):
        settings = NvidiaSettings()
        assert settings.base_url == "https://integrate.api.nvidia.com/v1"

    def test_default_timeout(self):
        settings = NvidiaSettings()
        assert settings.timeout_seconds == 60

    def test_default_api_key_is_empty(self, monkeypatch):
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        settings = NvidiaSettings()
        assert settings.api_key == ""
        assert settings.has_api_key is False

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "sk-test-key")
        settings = NvidiaSettings()
        assert settings.api_key == "sk-test-key"
        assert settings.has_api_key is True

    def test_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_BASE_URL", "https://custom.example.com/v1")
        settings = NvidiaSettings()
        assert settings.base_url == "https://custom.example.com/v1"

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_TIMEOUT_SECONDS", "120")
        settings = NvidiaSettings()
        assert settings.timeout_seconds == 120

    def test_model_mapping_lightning(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_MODEL_LIGHTNING", "nemotron-3.5-lightning")
        settings = NvidiaSettings()
        assert settings.model_for(ModelProfile.LIGHTNING) == "nemotron-3.5-lightning"

    def test_model_mapping_super(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_MODEL_SUPER", "nemotron-3-super")
        settings = NvidiaSettings()
        assert settings.model_for(ModelProfile.SUPER) == "nemotron-3-super"

    def test_model_mapping_ultra(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_MODEL_ULTRA", "nemotron-3-ultra")
        settings = NvidiaSettings()
        assert settings.model_for(ModelProfile.ULTRA) == "nemotron-3-ultra"

    def test_model_mapping_unset_returns_none(self):
        settings = NvidiaSettings()
        assert settings.model_for(ModelProfile.LIGHTNING) is None
        assert settings.model_for(ModelProfile.SUPER) is None
        assert settings.model_for(ModelProfile.ULTRA) is None


class TestNvidiaProviderConfig:
    def test_auto_rejected_by_resolve_model(self):
        provider = NvidiaProvider()
        with pytest.raises(InvalidModelProfileError):
            provider.resolve_model(ModelProfile.AUTO)

    def test_missing_model_raises_unavailable(self):
        provider = NvidiaProvider()
        with pytest.raises(ProviderUnavailableError):
            provider.resolve_model(ModelProfile.LIGHTNING)

    def test_missing_model_message_contains_profile(self):
        provider = NvidiaProvider()
        with pytest.raises(ProviderUnavailableError, match="lightning"):
            provider.resolve_model(ModelProfile.LIGHTNING)

    def test_configured_model_returns_id(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "sk-test")
        monkeypatch.setenv("NVIDIA_MODEL_SUPER", "nemotron-3-super")
        provider = NvidiaProvider()
        assert provider.resolve_model(ModelProfile.SUPER) == "nemotron-3-super"

    def test_health_check_returns_false(self):
        provider = NvidiaProvider()
        import asyncio

        assert asyncio.run(provider.health_check()) is False

    def test_generate_raises_not_implemented(self):
        import asyncio

        provider = NvidiaProvider()
        with pytest.raises(NotImplementedError):
            asyncio.run(provider.generate(None))  # type: ignore[arg-type]

    def test_stream_raises_not_implemented(self):
        import asyncio

        provider = NvidiaProvider()
        with pytest.raises(NotImplementedError):
            asyncio.run(provider.stream(None).__anext__())  # type: ignore[arg-type]