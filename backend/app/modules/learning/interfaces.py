"""Contracts for learning from user feedback and system telemetry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class FeedbackRating(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INCORRECT = "incorrect"


@dataclass(frozen=True, slots=True)
class Feedback:
    """A user's judgement on a generated answer."""

    query_id: str
    rating: FeedbackRating
    comment: str | None = None


class FeedbackLearner(ABC):
    """Records feedback and adapts retrieval/ranking parameters."""

    @abstractmethod
    async def record(self, feedback: Feedback) -> None: ...

    @abstractmethod
    async def adapt(self) -> None:
        """Apply accumulated feedback to tune system behaviour."""
