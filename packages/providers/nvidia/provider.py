"""
NVIDIA provider — architecture placeholder.

``NvidiaProvider`` is provided as a minimal stub so the provider
registry can accept it and downstream tests and documentation can
reference it.  ``generate()`` and ``stream()`` raise
``NotImplementedError``; ``health_check()`` returns ``False`` — this
is intentional and signals that the real integration is a future
sprint.

NVIDIA API integration is planned but **not implemented** in this
phase.  No network calls, no API keys, and no guessed model IDs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from packages.providers.base import (
    AIProvider,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
)
from packages.providers.exceptions import InvalidModelProfileError, ProviderUnavailableError
from packages.providers.models import ModelProfile
from packages.providers.nvidia.config import NvidiaSettings


class NvidiaProvider(AIProvider):
    """Placeholder for the future NVIDIA Nemotron provider.

    ``generate()`` and ``stream()`` raise ``NotImplementedError``
    because the real integration is not yet built.
    ``health_check()`` returns ``False``.
    """

    name: str = "nvidia"
    capabilities: frozenset[ProviderCapability] = frozenset(
        {
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.STREAMING,
        }
    )

    def __init__(self, settings: NvidiaSettings | None = None) -> None:
        self._settings = settings or NvidiaSettings()

    def resolve_model(self, profile: ModelProfile) -> str:
        """Return the NVIDIA model ID for *profile*.

        Raises ``InvalidModelProfileError`` when ``AUTO`` is passed —
        AUTO must be resolved to a concrete profile by the
        ``ModelSelector`` before reaching the provider.

        Raises ``ProviderUnavailableError`` when no model ID has been
        configured for the resolved profile.
        """
        if profile is ModelProfile.AUTO:
            raise InvalidModelProfileError("AUTO must be resolved before reaching the provider")

        model_id = self._settings.model_for(profile)
        if not model_id:
            raise ProviderUnavailableError(
                f"No NVIDIA model ID configured for profile '{profile.value}'"
            )
        return model_id

    async def generate(self, request: ProviderRequest) -> ProviderResponse:  # noqa: ARG002
        raise NotImplementedError(
            "NVIDIA API integration is planned but not implemented yet"
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        raise NotImplementedError(
            "NVIDIA API integration is planned but not implemented yet"
        )
        yield  # pragma: no cover

    async def health_check(self) -> bool:
        return False
