"""
Application configuration for deRek AI OS API.

Configuration is loaded from environment variables (and an optional .env
file during local development). No secrets are ever hardcoded here -
every sensitive or environment-specific value must come from the
environment.
"""

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are resolved in the following order of precedence:
    1. Actual environment variables (highest priority)
    2. Values defined in a local .env file
    3. The defaults declared below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application identity -------------------------------------------------
    APP_NAME: str = Field(default="deRek AI OS")
    APP_VERSION: str = Field(default="0.0.1")
    ENVIRONMENT: str = Field(default="development")

    # --- Server -----------------------------------------------------------------
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # --- API ----------------------------------------------------------------------
    API_PREFIX: str = Field(default="/api/v1")
    DOCS_URL: str = Field(default="/docs")
    REDOC_URL: str = Field(default="/redoc")
    OPENAPI_URL: str = Field(default="/openapi.json")

    # --- CORS -----------------------------------------------------------------------
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- Logging -----------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")
    LOG_JSON: bool = Field(default=True)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, value):
        """Allow CORS_ORIGINS to be provided as a comma-separated string
        in the environment, e.g. CORS_ORIGINS=http://localhost:5173,http://localhost:3000
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper() if isinstance(value, str) else value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    lru_cache ensures the environment/`.env` file is parsed only once per
    process, while still allowing tests to override dependencies via
    FastAPI's dependency-injection system.
    """
    return Settings()
