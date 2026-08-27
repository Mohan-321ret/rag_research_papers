"""Health endpoint. All logic lives in HealthService."""

from fastapi import APIRouter

from app.api.deps import HealthServiceDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def get_health(service: HealthServiceDep) -> HealthResponse:
    """Report API liveness and the status of backing services."""
    return await service.get_health()
