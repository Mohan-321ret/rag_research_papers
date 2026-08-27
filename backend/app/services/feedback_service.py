"""Answer feedback service (Phase 15).

The human signal Module 10 (continuous learning) will train on: was this
answer actually useful? Kept deliberately thin — record it against a real
answer, audit it, and expose it in the analytics aggregates.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.interaction_repository import InteractionRepository
from app.schemas.feedback import FeedbackRead, FeedbackRequest

logger = get_logger(__name__)


class FeedbackService:
    def __init__(
        self,
        session: AsyncSession,
        interaction_repository: InteractionRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self._session = session
        self._interactions = interaction_repository
        self._audit = audit_repository

    async def submit(self, *, user: User, request: FeedbackRequest) -> FeedbackRead:
        answer = await self._interactions.get_answer(request.answer_id)
        if answer is None:
            raise NotFoundError("Answer not found")

        entry = await self._interactions.create_feedback(
            answer_id=request.answer_id,
            user_id=user.id,
            rating=request.rating,
            comment=request.comment,
        )
        await self._audit.record(
            action="feedback.submit",
            user_id=user.id,
            resource_type="answer",
            resource_id=str(request.answer_id),
            details={"rating": request.rating.value},
        )
        await self._session.commit()
        logger.info(
            "feedback_recorded",
            answer_id=str(request.answer_id),
            rating=request.rating.value,
        )
        return FeedbackRead.model_validate(entry)
