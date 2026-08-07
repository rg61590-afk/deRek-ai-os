"""Version endpoint.

Exposes the running application name, version, and environment so
clients (and operators) can confirm exactly what is deployed.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from config import Settings, get_settings
from schemas import StandardResponse

router = APIRouter(tags=["version"])


class VersionData(BaseModel):
    name: str
    version: str
    environment: str


@router.get(
    "/version",
    response_model=StandardResponse[VersionData],
    summary="Version info",
    description="Returns the application name, version, and running environment.",
)
async def get_version(
    request: Request, settings: Settings = Depends(get_settings)
) -> StandardResponse[VersionData]:
    return StandardResponse.ok(
        data=VersionData(
            name=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT,
        ),
        message="Version retrieved",
        request_id=request.state.request_id,
    )
