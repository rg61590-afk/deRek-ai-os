"""
Request ID middleware for deRek AI OS.

Assigns a correlation ID to every incoming request, exposes it to
route handlers and exception handlers via `request.state.request_id`,
echoes it back on the response, and logs the full request/response
lifecycle.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from logger import logger

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request ID to every incoming request and logs
    the request/response lifecycle.

    - Uses the caller-supplied `X-Request-ID` header when present (so
      request IDs can be correlated across services), otherwise
      generates a new UUID4.
    - Stores the ID on `request.state.request_id` so route handlers and
      exception handlers can access it.
    - Echoes the ID back on the `X-Request-ID` response header.
    - Logs one structured line for the incoming request and one for the
      completed response (with status code and duration).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        started_at = time.perf_counter()

        logger.info(
            "request.received",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
