"""
Global exception handling for deRek AI OS API.

Ensures every error response — an unhandled exception, an explicit
`HTTPException`, or a request validation failure — comes back in the
same `StandardResponse` envelope used by successful responses, and
that every exception is logged with full request context.
"""

import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from logger import logger
from schemas import StandardResponse


def _request_id(request: Request) -> str:
    """Best-effort retrieval of the current request's correlation ID.

    Falls back to generating a fresh one if, for any reason, the
    request never passed through `RequestIDMiddleware`.
    """
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the given app.

    Called once from `main.create_app()`.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = _request_id(request)

        logger.warning(
            "http_exception",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        )

        envelope = StandardResponse.error(message=str(exc.detail), request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id(request)

        logger.warning(
            "validation_error",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "errors": exc.errors(),
            },
        )

        envelope = StandardResponse.error(
            message="Request validation failed",
            data={"errors": exc.errors()},
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler that guarantees clients always receive a
        well-formed JSON error body instead of a bare 500 with a stack
        trace leaking into the response.
        """
        request_id = _request_id(request)

        logger.error(
            "unhandled_exception",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
            },
            exc_info=exc,
        )

        envelope = StandardResponse.error(message="Internal server error", request_id=request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(),
        )
