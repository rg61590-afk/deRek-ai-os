"""Health check endpoint.

Used by load balancers, container orchestrators, and uptime monitors to
determine whether this process is alive and able to serve traffic.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from schemas import StandardResponse

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: str


@router.get(
    "/health",
    response_model=StandardResponse[HealthData],
    summary="Health check",
    description="Returns the current liveness status of the API process.",
)
async def get_health(request: Request) -> StandardResponse[HealthData]:
    return StandardResponse.ok(
        data=HealthData(status="ok"),
        message="Service is healthy",
        request_id=request.state.request_id,
    )
