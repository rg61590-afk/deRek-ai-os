"""Top-level API router.

Aggregates all versioned sub-routers under a single object that gets
mounted onto the FastAPI application with the configured API prefix.
"""

from fastapi import APIRouter

from routers import health, tasks, version

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(version.router)
api_router.include_router(tasks.router)
