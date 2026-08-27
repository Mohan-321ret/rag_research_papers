"""Query lifecycle: queries, retrieval logs, answers, citations, feedback."""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Query(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "queries"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    query_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(50))

    answers: Mapped[list["Answer"]] = relationship(back_populates="query", lazy="selectin")


class RetrievalLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One retrieved chunk (with rank/score) for one query — the evidence trail."""

    __tablename__ = "retrieval_logs"

    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int]
    score: Mapped[float]
    retriever: Mapped[str] = mapped_column(String(50))


class Answer(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "answers"

    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), index=True
    )
    answer_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    latency_ms: Mapped[float | None]
    # Verification outcome (Phase 4).
    grounded: Mapped[bool | None]
    confidence: Mapped[float | None]

    query: Mapped[Query] = relationship(back_populates="answers")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="answer", cascade="all, delete-orphan", lazy="selectin"
    )


class Citation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "citations"

    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    marker: Mapped[int]
    snippet: Mapped[str | None] = mapped_column(Text)

    answer: Mapped[Answer] = relationship(back_populates="citations")


class FeedbackRating(StrEnum):
    HELPFUL = "HELPFUL"
    NOT_HELPFUL = "NOT_HELPFUL"
    INCORRECT = "INCORRECT"


class Feedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "feedback"

    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    rating: Mapped[FeedbackRating] = mapped_column(
        Enum(FeedbackRating, native_enum=False, length=20)
    )
    comment: Mapped[str | None] = mapped_column(Text)
