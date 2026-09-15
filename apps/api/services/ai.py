"""
Application service layer for AI provider execution in deRek AI OS.

This module provides a provider-agnostic service that:

1. Resolves AUTO model selection through ModelSelector
2. Looks up the appropriate provider through ProviderRegistry
3. Constructs a ProviderRequest
4. Invokes the provider
5. Returns a ProviderResponse

No HTTP-specific concerns are present here — this is pure application
logic. The router layer is responsible for HTTP request/response mapping,
exception translation, and the StandardResponse envelope.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI

from packages.providers.base import (
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from packages.providers.exceptions import ProviderError, ProviderUnavailableError
from packages.providers.models import ModelMetadata, ModelProfile
from packages.providers.nvidia.config import NvidiaSettings
from packages.providers.nvidia.provider import NvidiaProvider
from packages.providers.registry import ProviderRegistry
from packages.providers.selector import ModelSelector


# ---------------------------------------------------------------------------
# Profile metadata used by the ModelSelector for AUTO routing.
# These descriptions and keyword tags match the project's documented
# model profiles (see docs/PROJECT_BIBLE.md).
# ---------------------------------------------------------------------------

_PROFILE_METADATA: dict[ModelProfile, ModelMetadata] = {
    ModelProfile.AUTO: ModelMetadata(
        profile=ModelProfile.AUTO,
        description="Automatic selection based on message content.",
        recommended_for=[],
    ),
    ModelProfile.LIGHTNING: ModelMetadata(
        profile=ModelProfile.LIGHTNING,
        description="Fast / lightweight — quick answers and simple tasks.",
        recommended_for=["quick", "simple", "fast", "short", "info", "easy"],
    ),
    ModelProfile.SUPER: ModelMetadata(
        profile=ModelProfile.SUPER,
        description="Balanced / default — general-purpose coding, reasoning, planning.",
        recommended_for=["normal", "coding", "help", "general", "task", "write"],
    ),
    ModelProfile.ULTRA: ModelMetadata(
        profile=ModelProfile.ULTRA,
        description="Maximum reasoning — deep analysis, complex planning, multi-step tasks.",
        recommended_for=["complex", "architecture", "reasoning", "planning", "difficult", "deep"],
    ),
}


@lru_cache(maxsize=1)
def get_model_selector() -> ModelSelector:
    """Return the application-scoped ModelSelector.

    Uses the project's default profile metadata and a SUPER fallback.
    The lru_cache ensures this is instantiated once per process.
    """
    return ModelSelector(profiles=dict(_PROFILE_METADATA), default_profile=ModelProfile.SUPER)


# ---------------------------------------------------------------------------
# ProviderRegistry lifecycle
# ---------------------------------------------------------------------------


def init_provider_registry(app: FastAPI) -> None:
    """Initialize the application-scoped ProviderRegistry and store it on app.state.

    This is called during FastAPI lifespan startup. The registry is populated
    with the NVIDIA provider (configured from environment variables) and stored
    as ``app.state.provider_registry`` so that request handlers can access it
    without creating a new registry per request.

    The function is idempotent: calling it again on the same ``app`` instance
    does not create a duplicate registration. Separate FastAPI application
    instances each maintain their own independent registry.

    Parameters
    ----------
    app:
        The FastAPI application instance. The registry is stored as
        ``app.state.provider_registry``.
    """
    if getattr(app.state, "provider_registry", None) is not None:
        # Already initialized on this app instance — avoid double registration.
        return

    registry = ProviderRegistry()
    settings = NvidiaSettings()
    provider = NvidiaProvider(settings=settings)
    registry.register(provider)
    app.state.provider_registry = registry


def get_provider_registry_from_app(app: FastAPI) -> ProviderRegistry:
    """Return the ProviderRegistry stored in app.state.

    This should be called from within a request handler, where ``app``
    is accessible via the FastAPI dependency injection system or via
    the router's ``app`` reference.

    Raises
    ------
    RuntimeError
        If the registry has not been initialized (init_provider_registry
        was not called during startup).
    """
    registry = getattr(app.state, "provider_registry", None)
    if registry is None:
        raise RuntimeError(
            "ProviderRegistry has not been initialized. "
            "Ensure init_provider_registry(app) is called during startup."
        )
    return registry


def resolve_model_profile(
    selector: ModelSelector,
    message: str,
    preferred: str | ModelProfile = ModelProfile.AUTO,
) -> ModelProfile:
    """Resolve the user's preferred model to a concrete ModelProfile.

    Parameters
    ----------
    selector:
        The ModelSelector to use for AUTO resolution.
    message:
        The user's input text. Used only when preferred is AUTO.
    preferred:
        A ModelProfile member or its string value. AUTO triggers keyword-based
        selection; any explicit profile is returned as-is.

    Returns
    -------
    ModelProfile
        The resolved profile. Never AUTO — AUTO is always resolved to a
        concrete profile by this function.
    """
    return selector.select(message=message, preferred=preferred)


def build_provider_request(
    messages: list[tuple[str, str]],
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ProviderRequest:
    """Construct a ProviderRequest from application-level parameters.

    Parameters
    ----------
    messages:
        List of (role, content) tuples. Roles are typically "system", "user",
        or "assistant".
    model:
        The resolved model profile name (e.g. "lightning", "super", "ultra").
        Must NOT be "auto" — AUTO must be resolved before calling this function.
    temperature:
        Optional sampling temperature (0.0–2.0).
    max_tokens:
        Optional maximum tokens to generate.

    Returns
    -------
    ProviderRequest
        A provider-agnostic request ready for AIProvider.generate().
    """
    provider_messages = [
        ProviderMessage(role=role, content=content) for role, content in messages
    ]
    return ProviderRequest(
        messages=provider_messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def generate_ai_response(
    selector: ModelSelector,
    registry: ProviderRegistry,
    messages: list[tuple[str, str]],
    preferred_model: str | ModelProfile = ModelProfile.AUTO,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[ProviderResponse, str, ModelProfile]:
    """Generate an AI response through the provider pipeline.

    This is the core orchestration function. It:

    1. Resolves AUTO through ModelSelector (if needed)
    2. Looks up the NVIDIA provider through ProviderRegistry
    3. Builds a ProviderRequest with the resolved model
    4. Invokes provider.generate()
    5. Returns the ProviderResponse, provider name, and resolved ModelProfile

    The resolved ModelProfile is the logical profile (lightning, super, ultra)
    determined before the provider call. It is returned so that callers can
    use it directly in the public API response without reverse-mapping from
    any provider-specific model ID.

    Parameters
    ----------
    selector:
        The ModelSelector for AUTO resolution.
    registry:
        The ProviderRegistry for provider lookup.
    messages:
        List of (role, content) tuples forming the conversation.
    preferred_model:
        The user's preferred model profile. AUTO triggers keyword-based
        selection; explicit profiles bypass AUTO.
    temperature:
        Optional sampling temperature override.
    max_tokens:
        Optional max tokens override.

    Returns
    -------
    tuple[ProviderResponse, str, ModelProfile]
        The provider's response, the provider's name, and the resolved
        logical ModelProfile.

    Raises
    ------
    InvalidModelProfileError
        If preferred_model is an unrecognized profile string.
    ProviderNotFoundError
        If the resolved provider is not registered.
    ProviderUnavailableError
        If the provider cannot serve the request (missing credentials,
        API errors, etc.).
    """
    # Resolve AUTO → concrete profile
    resolved_profile = resolve_model_profile(
        selector=selector,
        message=_last_user_message(messages),
        preferred=preferred_model,
    )

    # Look up the provider. For Sprint 4, the registry contains only NVIDIA,
    # but the lookup is by capability-appropriate name rather than hardcoded.
    provider = registry.get("nvidia")
    provider_name = provider.name

    # Build the provider-agnostic request using the resolved profile's value
    request = build_provider_request(
        messages=messages,
        model=resolved_profile.value,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Delegate to the provider
    provider_response = await provider.generate(request)
    return provider_response, provider_name, resolved_profile


def _last_user_message(messages: list[tuple[str, str]]) -> str:
    """Extract the last user message for AUTO selection heuristics."""
    for role, content in reversed(messages):
        if role == "user":
            return content
    # Fallback: concatenate all user messages, or the first message
    for role, content in messages:
        if role == "user":
            return content
    return messages[0][1] if messages else ""
