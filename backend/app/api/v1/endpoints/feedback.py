"""Answer feedback endpoint. All logic lives in FeedbackService."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, FeedbackServiceDep
from app.schemas.feedback import FeedbackRead, FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=FeedbackRead,
    status_code=status.HTTP_201_CREATED,
    summary="Rate a generated answer (the signal continuous learning trains on)",
)
async def submit_feedback(
    request: FeedbackRequest, service: FeedbackServiceDep, user: CurrentUserDep
) -> FeedbackRead:
    return await service.submit(user=user, request=request)
