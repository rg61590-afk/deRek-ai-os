"""
NVIDIA provider — architecture placeholder only.

``NvidiaProvider`` is provided as a minimal stub so the provider
registry can accept it and downstream tests and documentation can
reference it.  Calling any of its methods raises
``NotImplementedError`` — this is intentional and signals that the
real integration is a future sprint.

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
from packages.providers.exceptions import ProviderUnavailableError


class NvidiaProvider(AIProvider):
    """Placeholder for the future NVIDIA Nemotron provider.

    Class-level attributes follow the `AIProvider` contract, but every
    method raises ``NotImplementedError`` because the real integration
    is not yet built.
    """

    name: str = "nvidia"
    capabilities: frozenset[ProviderCapability] = frozenset(
        {
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.STREAMING,
        }
    )

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