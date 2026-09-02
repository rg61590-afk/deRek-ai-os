"""AI provider integrations for deRek AI OS.

Exposes the abstract `AIProvider` interface, the logical model-profile
domain (`ModelProfile`, `ModelMetadata`), the deterministic
`ModelSelector`, the `ProviderRegistry`, and a placeholder NVIDIA
provider package. No concrete provider is implemented in this release.
The current planned runtime provider is NVIDIA with the Nemotron model
family; the abstraction remains extensible for future providers.
"""

from .base import (
    AIProvider,
    ProviderCapability,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
)
from .exceptions import (
    InvalidModelProfileError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from .models import ModelMetadata, ModelProfile
from .registry import ProviderRegistry
from .selector import ModelSelector

__all__ = [
    "AIProvider",
    "InvalidModelProfileError",
    "ModelMetadata",
    "ModelProfile",
    "ModelSelector",
    "ProviderCapability",
    "ProviderError",
    "ProviderMessage",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderUnavailableError",
    "ProviderUsage",
]
