"""AI provider integrations for deRek AI OS.

Exposes the abstract `AIProvider` interface. No concrete provider
(Claude, Gemini, etc.) is implemented in this release.
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
