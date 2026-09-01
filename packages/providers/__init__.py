"""AI provider integrations for deRek AI OS.

Exposes the abstract `AIProvider` interface. No concrete provider
is implemented in this release. The current planned runtime provider
is NVIDIA with the Nemotron model family; the abstraction remains
extensible for future providers.
"""

from .base import (
    AIProvider,
    ProviderCapability,
    ProviderError,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ProviderUnavailableError,
    ProviderUsage,
)

__all__ = [
    "AIProvider",
    "ProviderCapability",
    "ProviderError",
    "ProviderMessage",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderUnavailableError",
    "ProviderUsage",
]
