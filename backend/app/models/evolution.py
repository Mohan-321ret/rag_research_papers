"""Knowledge evolution: the record of what changed between two versions
of a document (Module 3 — Change Detector / Diff Detector / Drift
Detector / Conflict Detector output), kept for every version transition
so a document's evolution can be inspected as a timeline.
"""

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class VersionComparison(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "version_comparisons"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    to_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE")
    )
    from_version_number: Mapped[int | None]
    to_version_number: Mapped[int]

    # "created" (no previous version) | "revised" (a real change to compare)
    change_type: Mapped[str] = mapped_column(String(20))

    # Diff Detector (text-level)
    text_similarity: Mapped[float] = mapped_column(Float)
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, default=0)
    replaced_count: Mapped[int] = mapped_column(Integer, default=0)
    added_sentences: Mapped[list[str]] = mapped_column(JSON, default=list)
    removed_sentences: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Drift Detector (semantic-level)
    drift_score: Mapped[float] = mapped_column(Float)
    drift_magnitude: Mapped[str] = mapped_column(String(20))  # none/minor/moderate/major

    # Conflict Detector (NLI over replaced sentence pairs)
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)

    # Incremental Re-indexer
    vectors_added: Mapped[int] = mapped_column(Integer, default=0)
    graph_synced: Mapped[bool] = mapped_column(Boolean, default=False)

    summary: Mapped[str] = mapped_column(Text)


class ConceptDriftReport(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Chunk-level concept drift (Phase 12): unlike ``VersionComparison``'s
    text diff (wording) and whole-document centroid drift (magnitude),
    this aligns each old chunk to its semantic nearest-neighbor new chunk
    by embedding cosine similarity and classifies *how* meaning shifted —
    rewording, expansion, narrowing, contradiction, or topic shift — not
    just whether it did. ``created_at`` (from ``CreatedAtMixin``) is the
    record's timestamp.
    """

    __tablename__ = "concept_drift_reports"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    old_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    new_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE")
    )
    old_version_number: Mapped[int | None]
    new_version_number: Mapped[int]

    drift_score: Mapped[float] = mapped_column(Float)  # mean over matched chunk pairs
    # dominant type among changed chunks: contradiction/narrowing/expansion/
    # topic_shift/rewording/removed/added/none
    drift_type: Mapped[str] = mapped_column(String(20))
    changed_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
