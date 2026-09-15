"""AI provider integrations for deRek AI OS.

Exposes the abstract ``AIProvider`` interface, the logical model-profile
domain (``ModelProfile``, ``ModelMetadata``), the deterministic
``ModelSelector``, the ``ProviderRegistry``, and the NVIDIA provider
implementation (``NvidiaProvider`` in the ``nvidia`` subpackage).
The abstraction remains extensible for future providers.
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
