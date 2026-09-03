"""
Async HTTP client for the NVIDIA provider.

This module provides ``NvidiaHttpClient``, a thin, reusable async
HTTP client that communicates with the NVIDIA API.  It handles
authentication, URL construction, timeout configuration, and
HTTP error translation — nothing else.

The client is deliberately provider-agnostic within the NVIDIA
domain: it knows how to send requests and translate responses, but
it does not contain model selection logic, business logic, or any
Task Engine concerns.
"""

from __future__ import annotations

from typing import Any

import httpx
from httpx import Timeout

from packages.providers.exceptions import ProviderUnavailableError
from packages.providers.nvidia.config import NvidiaSettings


class NvidiaHttpClient:
    """Async HTTP client for the NVIDIA API.

    Wraps ``httpx.AsyncClient`` with NVIDIA-specific configuration:
    base URL, authentication, and timeout.  HTTP errors are translated
    into the project's provider exception hierarchy so callers never
    need to catch ``httpx``-specific exceptions.

    Parameters
    ----------
    settings:
        NVIDIA configuration (API key, base URL, timeout).
    """

    def __init__(self, settings: NvidiaSettings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> NvidiaHttpClient:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def start(self) -> None:
        """Create the underlying ``httpx.AsyncClient`` (idempotent)."""
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(
            base_url=self._settings.base_url.rstrip("/"),
            headers=self._build_headers(),
            timeout=Timeout(self._settings.timeout_seconds),
        )

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient``."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict[str, str]:
        """Return request headers including Authorization.

        The API key is never included in log output or exception
        messages.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._settings.has_api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        return headers

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Translate HTTP error status codes into provider exceptions.

        Never includes the API key or Authorization header in error
        messages.
        """
        if response.is_success:
            return

        status = response.status_code

        if status in (401, 403):
            raise ProviderUnavailableError(
                "NVIDIA API authentication failed — check NVIDIA_API_KEY"
            )

        if status == 429:
            raise ProviderUnavailableError(
                "NVIDIA API rate limit exceeded — retry after backoff"
            )

        if status >= 500:
            raise ProviderUnavailableError(
                f"NVIDIA API server error (HTTP {status})"
            )

        raise ProviderUnavailableError(
            f"NVIDIA API request failed (HTTP {status})"
        )

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Send a POST request to the NVIDIA API.

        Parameters
        ----------
        path:
            API path (e.g. ``/chat/completions``).
        json:
            Optional JSON request body.
        params:
            Optional query parameters.

        Returns
        -------
        httpx.Response
            The raw response for successful requests.

        Raises
        ------
        ProviderUnavailableError
            On connection failures, timeouts, or HTTP error status codes.
            Also raised when no API key is configured (before any
            network call is made).
        """
        if not self._settings.has_api_key:
            raise ProviderUnavailableError(
                "NVIDIA_API_KEY is not configured — set it in the environment "
                "or .env file"
            )

        if self._client is None:
            raise ProviderUnavailableError(
                "NvidiaHttpClient has not been started — call start() "
                "or use as an async context manager"
            )

        clean_path = path if path.startswith("/") else f"/{path}"

        try:
            response = await self._client.post(
                clean_path, json=json, params=params
            )
        except httpx.TimeoutException:
            raise ProviderUnavailableError(
                "NVIDIA API request timed out"
            ) from None
        except httpx.ConnectError:
            raise ProviderUnavailableError(
                "NVIDIA API is unreachable"
            ) from None
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                "NVIDIA API request failed"
            ) from exc

        self._raise_for_status(response)
        return response
