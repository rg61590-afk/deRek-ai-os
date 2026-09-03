"""
NVIDIA provider configuration for deRek AI OS.

``NvidiaSettings`` is a ``pydantic_settings.BaseSettings`` subclass that
reads NVIDIA-specific configuration from environment variables and the
project's ``.env`` file.  No secrets are hardcoded — every value comes
from the environment or ``.env``, consistent with the application
configuration in ``apps/api/config.py``.

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

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.providers.models import ModelProfile


class NvidiaSettings(BaseSettings):
    """NVIDIA provider configuration loaded from environment / .env file.

    Values are resolved in the following order of precedence:
    1. Explicit constructor arguments (highest priority)
    2. Actual environment variables
    3. Values defined in the project's ``.env`` file
    4. The defaults declared below

    For tests that must not read the real ``.env`` file, use
    ``NvidiaSettings.for_testing()``.
    """

    model_config = SettingsConfigDict(
        env_prefix="NVIDIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_key: str = Field(default="")
    base_url: str = Field(default="https://integrate.api.nvidia.com/v1")
    timeout_seconds: int = Field(default=60)
    model_lightning: str | None = Field(default=None)
    model_super: str | None = Field(default=None)
    model_ultra: str | None = Field(default=None)

    @classmethod
    def for_testing(cls, **kwargs: Any) -> NvidiaSettings:
        """Create a settings instance without reading the real ``.env`` file.

        Pass explicit values as keyword arguments.  This bypasses the
        project's ``.env`` to prevent credential leakage in tests that
        assert on default values.
        """
        config = cls.model_config.copy()
        config["env_file"] = None  # type: ignore[typeddict-item]
        return cls(_env_file=None, **kwargs)

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
