"""Documents, their immutable versions, and retrievable chunks.

The version chain (documents -> document_versions -> document_chunks) is
the backbone of temporal knowledge management: every re-ingestion of a
source creates a new version, drift is measured between versions, and
historical queries can be answered against any past version.
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A logical knowledge source; its content lives in versions."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(500))
    source_uri: Mapped[str | None] = mapped_column(String(2000))
    source_type: Mapped[str] = mapped_column(String(50), default="upload")
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=20), default=DocumentStatus.PENDING
    )
    doc_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
        lazy="selectin",
    )


class DocumentVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An immutable snapshot of a document's content at ingestion time."""

    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int]
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(default=True)

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
        lazy="selectin",
    )


class DocumentChunk(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A retrievable unit of text belonging to one document version."""

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("version_id", "chunk_index"),)

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    # Denormalized for direct citation joins; version_id remains authoritative.
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None]
    page_number: Mapped[int | None]
    section: Mapped[str | None] = mapped_column(String(300))
    # Id of this chunk's vector in the FAISS index.
    embedding_ref: Mapped[str | None] = mapped_column(String(100), index=True)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    version: Mapped[DocumentVersion] = relationship(back_populates="chunks")
