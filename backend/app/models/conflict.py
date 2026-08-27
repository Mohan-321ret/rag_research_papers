"""Cross-document knowledge conflicts (Phase 13): two chunks from
*different* documents making contradictory claims, with the metadata-
based authority resolution that decided (or failed to decide) which one
should be preferred.
"""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class KnowledgeConflict(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_conflicts"

    claim_a_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    claim_a_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    claim_a_content: Mapped[str] = mapped_column(Text)

    claim_b_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True
    )
    claim_b_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    claim_b_content: Mapped[str] = mapped_column(Text)

    contradiction_score: Mapped[float] = mapped_column(Float)

    # Authority resolution outcome. Null/False when priority, date, and
    # version all tie — genuinely unresolved, not silently defaulted.
    preferred_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_reason: Mapped[str] = mapped_column(Text)
