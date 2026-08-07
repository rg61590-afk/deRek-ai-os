"""
Standard API response envelope for deRek AI OS.

Every endpoint response — success or error — conforms to this shape so
API consumers can rely on one consistent contract regardless of which
endpoint they call.
"""

from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class StandardResponse(BaseModel, Generic[DataT]):
    """Reusable API response envelope.

    Attributes:
        success: Whether the request was processed successfully.
        message: Short human-readable summary of the result.
        data: The endpoint-specific payload (None for errors, or when
            there is nothing to return).
        request_id: The correlation ID for this request, propagated
            from `RequestIDMiddleware` / the `X-Request-ID` header.
        timestamp: UTC timestamp (ISO 8601) at which the response was
            constructed.
    """

    success: bool
    message: str
    data: Optional[DataT] = None
    request_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def ok(
        cls,
        *,
        request_id: str,
        data: Optional[DataT] = None,
        message: str = "OK",
    ) -> "StandardResponse[DataT]":
        """Build a success envelope."""
        return cls(success=True, message=message, data=data, request_id=request_id)

    @classmethod
    def error(
        cls,
        *,
        message: str,
        request_id: str,
        data: Optional[DataT] = None,
    ) -> "StandardResponse[DataT]":
        """Build an error envelope."""
        return cls(success=False, message=message, data=data, request_id=request_id)
