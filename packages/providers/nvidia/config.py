"""
NVIDIA provider configuration for deRek AI OS.

Reads NVIDIA-specific settings from environment variables.  No secrets
are hardcoded — every value comes from the environment or a local
``.env`` file, consistent with the project's configuration architecture
(see ``apps/api/config.py``).

Required:
    NVIDIA_API_KEY

Optional:
    NVIDIA_BASE_URL       (default: https://integrate.api.nvidia.com/v1)
    NVIDIA_TIMEOUT_SECONDS (default: 60)
    NVIDIA_MODEL_LIGHTNING
    NVIDIA_MODEL_SUPER
    NVIDIA_MODEL_ULTRA
"""

from __future__ import annotations

from dataclasses import dataclass, field
from os import environ

from packages.providers.models import ModelProfile


@dataclass
class NvidiaSettings:
    """NVIDIA provider configuration loaded from environment variables."""

    api_key: str = field(default_factory=lambda: environ.get("NVIDIA_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: environ.get(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
    )
    timeout_seconds: int = field(
        default_factory=lambda: int(environ.get("NVIDIA_TIMEOUT_SECONDS", "60"))
    )
    model_lightning: str | None = field(
        default_factory=lambda: environ.get("NVIDIA_MODEL_LIGHTNING") or None
    )
    model_super: str | None = field(
        default_factory=lambda: environ.get("NVIDIA_MODEL_SUPER") or None
    )
    model_ultra: str | None = field(
        default_factory=lambda: environ.get("NVIDIA_MODEL_ULTRA") or None
    )

    @property
    def has_api_key(self) -> bool:
        """Return True when an API key has been configured."""
        return bool(self.api_key)

    def model_for(self, profile: ModelProfile) -> str | None:
        """Return the configured NVIDIA model ID for *profile*.

        Returns ``None`` when no model ID has been configured for the
        given profile.
        """
        mapping = {
            ModelProfile.LIGHTNING: self.model_lightning,
            ModelProfile.SUPER: self.model_super,
            ModelProfile.ULTRA: self.model_ultra,
        }
        return mapping.get(profile)
