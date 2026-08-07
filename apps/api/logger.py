"""
Structured logging configuration for deRek AI OS API.

Emits either human-readable console logs (development) or single-line
JSON logs (production/CI) depending on configuration, so log output can
be safely ingested by any log aggregation pipeline without additional
parsing rules.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from config import get_settings

_LOG_RECORD_RESERVED_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include any extra fields passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in _LOG_RECORD_RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter used for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def configure_logging() -> logging.Logger:
    """Configure root logging handlers exactly once and return the
    application logger.
    """
    settings = get_settings()
    root_logger = logging.getLogger()

    # Avoid duplicate handlers if configure_logging() is called more than once
    # (e.g. under test runners that import the app multiple times).
    if getattr(root_logger, "_derek_configured", False):
        return logging.getLogger("derek")

    root_logger.setLevel(settings.LOG_LEVEL)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter() if settings.LOG_JSON else ConsoleFormatter())

    # Remove any pre-existing handlers (e.g. installed by uvicorn) to avoid
    # duplicate log lines, then install our own.
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Keep uvicorn's own loggers propagating through the root handler instead
    # of installing their own formatters, so all output shares one format.
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    root_logger._derek_configured = True  # type: ignore[attr-defined]

    return logging.getLogger("derek")


logger = configure_logging()
