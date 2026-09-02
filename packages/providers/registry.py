"""
Provider registry for deRek AI OS.

Maintains a lookup table of registered `AIProvider` implementations.
Providers are registered once (typically at startup) and retrieved by
name when work needs to be dispatched. The registry also exposes a
`health_check_all` method so the API layer can report provider status
without knowing individual provider internals.
"""

from __future__ import annotations

from collections.abc import Iterator

from packages.providers.base import AIProvider
from packages.providers.exceptions import ProviderNotFoundError


class ProviderRegistry:
    """Thread-unsafe registry of named AI provider implementations.

    Designed to be instantiated once and populated at application
    startup. No I/O or network access occurs during registration.
    """

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}

    def register(self, provider: AIProvider) -> None:
        """Add *provider* to the registry under `provider.name`.

        Raises `ValueError` if a provider with the same name is already
        registered.
        """
        if provider.name in self._providers:
            raise ValueError(
                f"Provider '{provider.name}' is already registered"
            )
        self._providers[provider.name] = provider

    def get(self, name: str) -> AIProvider:
        """Return the provider registered under *name*.

        Raises `ProviderNotFoundError` when no provider with that name
        exists.
        """
        try:
            return self._providers[name]
        except KeyError:
            raise ProviderNotFoundError(name)

    def has(self, name: str) -> bool:
        """Return True if a provider with *name* is registered."""
        return name in self._providers

    def names(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._providers)

    def all(self) -> Iterator[AIProvider]:
        """Iterate over all registered providers."""
        return iter(self._providers.values())

    async def health_check_all(self) -> dict[str, bool]:
        """Run `health_check()` on every registered provider.

        Returns a mapping of provider name to reachability boolean.
        Providers that raise during their health check are marked
        False rather than propagating the exception, so a single bad
        provider cannot block status reporting for the rest.
        """
        results: dict[str, bool] = {}
        for name, provider in self._providers.items():
            try:
                results[name] = bool(await provider.health_check())
            except Exception:
                results[name] = False
        return results