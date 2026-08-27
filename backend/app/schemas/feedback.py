"""Schemas for answer feedback (Phase 15).

Feedback closes the loop for Module 10 (continuous learning): it is the
human signal about whether a generated answer was actually useful.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.interaction import FeedbackRating


class FeedbackRequest(BaseModel):
    answer_id: uuid.UUID
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    answer_id: uuid.UUID
    user_id: uuid.UUID | None
    rating: FeedbackRating
    comment: str | None
    created_at: datetime
