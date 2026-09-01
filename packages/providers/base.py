"""
Abstract AI provider interface for deRek AI OS.

This module defines the contract every AI provider integration must
implement in order to plug into the Kernel. It intentionally contains
no concrete provider implementation — that is out of scope for this
release. The interface is designed to be provider-agnostic so that
any AI provider compatible with the project's architecture can be
integrated without changing the Core System.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel, Field


class ProviderCapability(str, Enum):
    """Capabilities a provider implementation may declare support for."""

    TEXT_GENERATION = "text_generation"
    STREAMING = "streaming"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    EMBEDDINGS = "embeddings"


class ProviderMessage(BaseModel):
    """A single message in a provider-agnostic conversation."""

    role: str = Field(..., description="e.g. 'system', 'user', 'assistant'")
    content: str


class ProviderRequest(BaseModel):
    """Provider-agnostic request payload passed to `AIProvider.generate`
    and `AIProvider.stream`.
    """

    messages: list[ProviderMessage]
    model: Optional[str] = Field(
        default=None, description="Provider-specific model identifier"
    )
    max_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderUsage(BaseModel):
    """Token/usage accounting returned by a provider."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ProviderResponse(BaseModel):
    """Provider-agnostic response payload returned by `AIProvider.generate`."""

    content: str
    model: str
    usage: ProviderUsage = Field(default_factory=ProviderUsage)
    finish_reason: Optional[str] = None
    raw: dict[str, Any] = Field(
        default_factory=dict, description="Original provider payload, for debugging"
    )


class ProviderError(Exception):
    """Base exception raised by AI provider implementations."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider cannot currently serve requests."""


class AIProvider(ABC):
    """Abstract interface every AI provider integration must implement.

    Concrete implementations are intentionally out of scope for this
    release. This class exists so the Kernel and the rest of deRek AI OS
    can be developed against a stable contract before any provider is
    wired in. The abstraction remains extensible for future providers.
    """

    #: Human-readable provider name (e.g. "nvidia").
    name: str

    #: Capabilities this provider implementation supports.
    capabilities: frozenset[ProviderCapability] = frozenset()

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate a complete response for the given request.

        Implementations must raise `ProviderError` (or a subclass) on
        failure rather than leaking provider-specific exceptions.
        """
        raise NotImplementedError

    @abstractmethod
    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        """Stream a response for the given request, yielding text chunks
        as they become available.
        """
        raise NotImplementedError
        yield  # pragma: no cover - keeps this an async generator for type checkers

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is currently reachable and able
        to serve requests, False otherwise. Must not raise.
        """
        raise NotImplementedError

    def supports(self, capability: ProviderCapability) -> bool:
        """Return True if this provider declares support for `capability`."""
        return capability in self.capabilities
