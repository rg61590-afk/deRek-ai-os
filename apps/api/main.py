"""
deRek AI OS - API entrypoint.

This module wires together configuration, structured logging, and the
versioned API router into a single FastAPI application instance. It
intentionally contains no business logic - only application bootstrap.
"""

import sys
from pathlib import Path

# `packages/` lives at the repository root, one level above `apps/`, and
# is not (yet) an installed distribution (no root-level pyproject.toml).
# Add the repository root to sys.path so `packages.*` imports (used by
# routers/tasks.py) resolve regardless of whether this process was
# launched via `python main.py`, uvicorn, or pytest. Must run before any
# first-party import below that transitively imports `packages`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from exceptions import register_exception_handlers
from logger import logger
from middleware import RequestIDMiddleware
from routers.api import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Runs startup logic before the app begins accepting requests, and
    shutdown logic after it stops accepting new ones. This is the
    modern FastAPI replacement for the deprecated
    `@app.on_event("startup"/"shutdown")` decorators.
    """
    # --- Startup -------------------------------------------------------------
    logger.info(
        "startup.begin",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "host": settings.HOST,
            "port": settings.PORT,
        },
    )
    logger.info("startup.complete")

    yield

    # --- Shutdown ------------------------------------------------------------
    logger.info("shutdown.begin")
    logger.info("shutdown.complete")


def create_app() -> FastAPI:
    """Application factory.

    Using a factory (rather than a bare module-level `app`) keeps the
    module importable for tests and tooling without side effects beyond
    constructing the FastAPI instance.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        openapi_url=settings.OPENAPI_URL,
        lifespan=lifespan,
    )

    # Middleware order matters: the first middleware added is outermost,
    # so CORS wraps everything (including error responses), while
    # RequestIDMiddleware sits just inside it, guaranteeing
    # `request.state.request_id` is set before routing/exception
    # handling occurs.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIDMiddleware)

    application.include_router(api_router, prefix=settings.API_PREFIX)

    register_exception_handlers(application)

    @application.get("/", tags=["root"], summary="Root")
    async def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": settings.DOCS_URL,
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=not settings.is_production,
        log_config=None,  # defer entirely to our structured logger
    )
