"""Analytics endpoints. All logic lives in AnalyticsService."""

from fastapi import APIRouter

from app.api.deps import AnalyticsServiceDep, CurrentUserDep
from app.schemas.analytics import DashboardResponse, MetricsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Headline corpus / usage / answer-quality / drift numbers",
)
async def dashboard(
    service: AnalyticsServiceDep, _user: CurrentUserDep
) -> DashboardResponse:
    return await service.dashboard()


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Breakdowns behind the dashboard (by intent, retriever, entity type, ...)",
)
async def metrics(service: AnalyticsServiceDep, _user: CurrentUserDep) -> MetricsResponse:
    return await service.metrics()
