"""
NVIDIA provider — non-streaming text generation for deRek AI OS.

``NvidiaProvider`` implements ``AIProvider`` for NVIDIA NIM APIs.
``generate()`` performs non-streaming text generation via the
``NvidiaHttpClient``.  ``stream()`` remains unimplemented.
``health_check()`` returns ``False`` until a future sprint.

Dependency injection is supported for both ``NvidiaSettings`` and
``NvidiaHttpClient``, enabling testability without real network calls.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from packages.providers.base import (
    AIProvider,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
)
from packages.providers.exceptions import InvalidModelProfileError, ProviderUnavailableError
from packages.providers.models import ModelProfile
from packages.providers.nvidia.client import NvidiaHttpClient
from packages.providers.nvidia.config import NvidiaSettings


class NvidiaProvider(AIProvider):
    """NVIDIA Nemotron provider for non-streaming text generation.

    ``generate()`` sends requests to the NVIDIA NIM chat-completions
    endpoint and returns a ``ProviderResponse``.  ``stream()`` is not
    implemented yet.  ``health_check()`` returns ``False``.
    """

    name: str = "nvidia"
    capabilities: frozenset[ProviderCapability] = frozenset(
        {
            ProviderCapability.TEXT_GENERATION,
        }
    )

    def __init__(
        self,
        settings: NvidiaSettings | None = None,
        http_client: NvidiaHttpClient | None = None,
    ) -> None:
        """Initialize the provider.

        Parameters
        ----------
        settings:
            NVIDIA configuration.  Defaults to ``NvidiaSettings()``
            which reads from environment variables.
        http_client:
            Optional pre-configured ``NvidiaHttpClient``.  When
            provided, the provider uses it directly and does NOT
            manage its lifecycle.  When ``None``, the provider
            creates and manages its own client.
        """
        self._settings = settings or NvidiaSettings()
        self._http_client = http_client

    def resolve_model(self, profile: ModelProfile) -> str:
        """Return the NVIDIA model ID for *profile*.

        Raises ``InvalidModelProfileError`` when ``AUTO`` is passed —
        AUTO must be resolved to a concrete profile before reaching
        the provider.

        Raises ``ProviderUnavailableError`` when no model ID has been
        configured for the resolved profile.
        """
        if profile is ModelProfile.AUTO:
            raise InvalidModelProfileError("AUTO must be resolved before reaching the provider")

        model_id = self._settings.model_for(profile)
        if not model_id:
            raise ProviderUnavailableError(
                f"No NVIDIA model ID configured for profile '{profile.value}'"
            )
        return model_id

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate a complete response for the given request.

        Requires ``request.model`` to be set to a concrete model
        profile name (``lightning``, ``super``, or ``ultra``).
        The provider resolves the profile to a configured NVIDIA model
        ID, sends the request, and returns the response.
        """
        profile = self._resolve_profile(request)
        model_id = self.resolve_model(profile)

        # Lifecycle: provider manages the client only when it created it.
        client = self._http_client or NvidiaHttpClient(self._settings)
        owns_client = self._http_client is None
        try:
            if owns_client:
                await client.start()
            payload = self._build_payload(request, model_id)
            response = await client.post("/chat/completions", json=payload)
            data = response.json()
            return self._parse_response(data, model_id)
        finally:
            if owns_client:
                await client.aclose()

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        raise NotImplementedError(
            "NVIDIA API streaming integration is planned but not implemented yet"
        )
        yield  # pragma: no cover

    async def health_check(self) -> bool:
        return False

    def _resolve_profile(self, request: ProviderRequest) -> ModelProfile:
        """Derive the ModelProfile from ``request.model``.

        Raises ``InvalidModelProfileError`` when ``request.model`` is
        ``None``, ``AUTO``, or an unrecognised string — the provider
        must not silently fall back to a default profile.
        """
        if request.model is None:
            raise InvalidModelProfileError("request.model is required")

        try:
            profile = ModelProfile(request.model)
        except ValueError:
            raise InvalidModelProfileError(request.model)

        if profile is ModelProfile.AUTO:
            raise InvalidModelProfileError(
                "AUTO must be resolved to a concrete profile before reaching the provider"
            )

        return profile

    def _build_payload(
        self, request: ProviderRequest, model_id: str
    ) -> dict[str, object]:
        """Translate ``ProviderRequest`` into an NVIDIA API payload.

        Produces an OpenAI-compatible chat-completions payload.  Only
        parameters that exist on the current ``ProviderRequest`` are
        included.
        """
        messages: list[dict[str, str]] = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        payload: dict[str, object] = {
            "model": model_id,
            "messages": messages,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        return payload

    def _parse_response(
        self, data: dict[str, object], model_id: str
    ) -> ProviderResponse:
        """Translate an NVIDIA API response into ``ProviderResponse``.

        Handles missing, null, or malformed fields defensively.  Never
        exposes API keys, Authorization headers, or other secrets.
        """
        if not isinstance(data, dict):
            raise ProviderUnavailableError("NVIDIA API returned an unexpected response format")

        choices = data.get("choices")
        if choices is None:
            raise ProviderUnavailableError("NVIDIA API response is missing 'choices'")
        if not isinstance(choices, list):
            raise ProviderUnavailableError("NVIDIA API returned an unexpected response format")
        if not choices:
            raise ProviderUnavailableError("NVIDIA API returned an empty response")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ProviderUnavailableError("NVIDIA API returned a malformed choice")

        message = first_choice.get("message")
        if message is None:
            raise ProviderUnavailableError("NVIDIA API response choice is missing 'message'")
        if not isinstance(message, dict):
            raise ProviderUnavailableError("NVIDIA API returned a malformed message")

        content = message.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)

        finish_reason = first_choice.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            finish_reason = str(finish_reason)

        usage_data = data.get("usage")
        if not isinstance(usage_data, dict):
            usage_data = {}

        prompt_tokens = usage_data.get("prompt_tokens")
        completion_tokens = usage_data.get("completion_tokens")

        def _safe_int(value: object) -> int:
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
            return 0

        usage = ProviderUsage(
            input_tokens=_safe_int(prompt_tokens),
            output_tokens=_safe_int(completion_tokens),
        )

        return ProviderResponse(
            content=content,
            model=model_id,
            usage=usage,
            finish_reason=finish_reason,
            raw=data,
        )
