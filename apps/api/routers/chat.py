"""
Chat API endpoint for deRek AI OS.

Provides POST /api/v1/chat — the primary application-layer entry point
for AI text generation. Accepts a provider-agnostic request, resolves
the model profile through ModelSelector, dispatches to the NVIDIA provider,
and returns the response in the standard envelope.

No NVIDIA-specific identifiers, API keys, or internal implementation
details are exposed through this endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from packages.providers.exceptions import (
    InvalidModelProfileError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from schemas import StandardResponse
from services.ai import (
    generate_ai_response,
    get_model_selector,
    get_provider_registry_from_app,
)

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str = Field(
        ...,
        description="Message role: 'system', 'user', or 'assistant'.",
        examples=["user"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Message text content. Must not be empty.",
        examples=["Explain quantum computing in simple terms."],
    )

    @field_validator("role")
    @classmethod
    def _valid_role(cls, value: str) -> str:
        allowed = {"system", "user", "assistant"}
        if value not in allowed:
            raise ValueError(
                f"role must be one of {sorted(allowed)}, got '{value}'"
            )
        return value


class ChatRequest(BaseModel):
    """Request body for POST /api/v1/chat."""

    model_config = {"str_strip_whitespace": True}

    messages: list[ChatMessage] = Field(
        ...,
        description="Conversation messages. The last user message is used "
                    "for AUTO model selection.",
        min_length=1,
    )
    model: str = Field(
        default="auto",
        description="Model profile: 'auto', 'lightning', 'super', or 'ultra'.",
        examples=["auto"],
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0–2.0). Defaults to provider default.",
        examples=[0.7],
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Maximum tokens to generate. Defaults to provider default.",
        examples=[1024],
    )

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        allowed = {"auto", "lightning", "super", "ultra"}
        if value not in allowed:
            raise ValueError(
                f"model must be one of {sorted(allowed)}, got '{value}'"
            )
        return value


class UsageData(BaseModel):
    """Token usage information for a generation."""

    input_tokens: int = 0
    output_tokens: int = 0


class ChatResponseData(BaseModel):
    """Response payload for a successful chat completion."""

    content: str = Field(description="Generated text content.")
    selected_model: str = Field(
        description="The logical model profile used for this request "
                    "(e.g. 'lightning', 'super', 'ultra').",
        examples=["super"],
    )
    provider: str = Field(
        description="The provider that served this request.",
        examples=["nvidia"],
    )
    usage: UsageData = Field(
        description="Token usage for this generation.",
    )
    finish_reason: str | None = Field(
        default=None,
        description="Why generation stopped (e.g. 'stop', 'length').",
        examples=["stop"],
    )


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@router.post(
    "/chat",
    response_model=StandardResponse[ChatResponseData],
    status_code=status.HTTP_200_OK,
    summary="AI chat completion",
    description=(
        "Send a chat conversation and receive a generated response. "
        "Model selection supports 'auto' (keyword-based heuristic) or "
        "explicit profiles: 'lightning', 'super', 'ultra'. "
        "No NVIDIA API keys or internal implementation details are exposed."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid model profile or request validation error.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Provider is unavailable (missing credentials, API error, etc.).",
        },
    },
)
async def chat_completion(
    payload: ChatRequest,
    request: Request,
) -> StandardResponse[ChatResponseData]:
    """Process a chat completion request through the AI provider pipeline."""
    selector = get_model_selector()
    registry = get_provider_registry_from_app(request.app)

    # Convert API request messages to the service layer's tuple format
    messages = [(msg.role, msg.content) for msg in payload.messages]

    try:
        response, provider_name, resolved_profile = await generate_ai_response(
            selector=selector,
            registry=registry,
            messages=messages,
            preferred_model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except Exception as exc:
        # Map provider-domain exceptions to appropriate HTTP status codes.
        # ProviderError covers InvalidModelProfileError (400) and
        # ProviderUnavailableError (503).
        if isinstance(exc, InvalidModelProfileError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model profile: {exc.value}",
            ) from exc

        if isinstance(exc, ProviderNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No AI provider is currently registered.",
            ) from exc

        if isinstance(exc, ProviderUnavailableError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The AI provider is currently unavailable.",
            ) from exc

        # Catch-all for any other ProviderError subclasses
        if isinstance(exc, ProviderError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider error.",
            ) from exc

        # Re-raise non-provider exceptions for the global handler
        raise

    # Use the already-resolved logical ModelProfile directly.
    # No reverse-mapping from provider model IDs is needed.
    selected_model = resolved_profile.value

    response_data = ChatResponseData(
        content=response.content,
        selected_model=selected_model,
        provider=provider_name,
        usage=UsageData(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        ),
        finish_reason=response.finish_reason,
    )

    return StandardResponse.ok(
        data=response_data,
        message="Chat completion generated",
        request_id=request.state.request_id,
    )
