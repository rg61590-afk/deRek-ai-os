"""
Global exception handling for deRek AI OS API.

Ensures every error response — an unhandled exception, an explicit
`HTTPException`, or a request validation failure — comes back in the
same `StandardResponse` envelope used by successful responses, and
that every exception is logged with full request context.
"""

import uuid
from typing import Any, Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from http import HTTPStatus
from starlette.exceptions import HTTPException as StarletteHTTPException

from logger import logger
from schemas import StandardResponse


def _request_id(request: Request) -> str:
    """Best-effort retrieval of the current request's correlation ID.

    Falls back to generating a fresh one if, for any reason, the
    request never passed through `RequestIDMiddleware`.
    """
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _json_safe(value: Any) -> Any:
    """Recursively convert `value` into a JSON-serializable structure.

    Pydantic v2 validation errors raised by a custom `field_validator`
    that itself raises a plain `ValueError` (as `validate_capability`
    and `validate_task_name` in `packages/tasks/models.py` do) embed
    that original exception instance in the error dict's `ctx["error"]`
    field, so the error message can be interpolated at render time.
    That's expected and correct from Pydantic's side — but an exception
    instance is not JSON-serializable, and Starlette's `JSONResponse`
    calls `json.dumps` with no `default=` fallback (unlike this
    project's own `JSONFormatter` in `logger.py`, which passes
    `default=str`). Returning `exc.errors()` verbatim inside a
    `JSONResponse` therefore fails at serialization time.

    This walks the error structure and replaces anything that isn't
    already a JSON-safe primitive with its string form, preserving the
    error's shape and message content without losing information.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    # Exception instances (e.g. the ValueError raised by a validator,
    # embedded in ctx["error"]) and anything else FastAPI/Pydantic
    # might attach to an error (bytes, custom types) are not
    # JSON-native — represent them as their string form rather than
    # let them fail at encoding time.
    return str(value)


def _sanitize_validation_errors(errors: Sequence[Any]) -> list[Any]:
    """Return a JSON-safe copy of a Pydantic/FastAPI validation error
    list, suitable for both structured logging and the response
    envelope. Never mutates `errors` or the dicts within it.
    """
    return [_json_safe(error) for error in errors]


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

        # Sanitize before logging AND before building the response
        # envelope, so both carry the exact same JSON-safe error
        # structure rather than the raw, potentially-unserializable
        # one from Pydantic. See `_json_safe` for why this is needed.
        sanitized_errors = _sanitize_validation_errors(exc.errors())

        logger.warning(
            "validation_error",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "errors": sanitized_errors,
            },
        )

        envelope = StandardResponse.error(
            message="Request validation failed",
            data={"errors": sanitized_errors},
            request_id=request_id,
        )
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
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
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(),
        )
