"""
Provider-domain exceptions for deRek AI OS.

Each package in `packages/` owns its own exception hierarchy. The
API layer is expected to translate these into `fastapi.HTTPException`
at the router boundary so they flow through the existing global
exception handling and `StandardResponse` envelope rather than
needing handlers of their own.
"""


class ProviderError(Exception):
    """Base exception for all provider-domain errors."""


class ProviderUnavailableError(ProviderError):
    """Raised when a registered provider cannot currently serve requests.

    Used by the registry/health-check layer when a provider has been
    registered but its underlying service is unreachable or has been
    disabled. Distinct from `ProviderNotFound`, which signals that no
    provider with the requested name is registered at all.
    """


class ProviderNotFoundError(ProviderError):
    """Raised when a provider lookup fails because no provider with the
    requested name is registered in the `ProviderRegistry`.
    """

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Provider '{provider_name}' is not registered")


class InvalidModelProfileError(ProviderError):
    """Raised when a string cannot be parsed into a valid `ModelProfile`.

    Carries the offending value so callers and tests can assert on it
    without having to scrape the exception message.
    """

    def __init__(self, value: object) -> None:
        self.value = value
        super().__init__(f"'{value}' is not a valid model profile")