"""Data access for documents and their versions."""

import uuid
from typing import Any

from sqlalchemy import func, select, update

from app.models.document import Document, DocumentStatus, DocumentVersion
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    async def get(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def get_by_filename(
        self, *, created_by_id: uuid.UUID, filename: str
    ) -> Document | None:
        """Find the caller's document for this filename (version matching)."""
        result = await self._session.execute(
            select(Document).where(
                Document.created_by_id == created_by_id,
                Document.source_uri == filename,
            )
        )
        return result.scalars().first()

    async def list_documents(
        self, *, limit: int, offset: int, search: str | None = None
    ) -> tuple[list[Document], int]:
        query = select(Document)
        if search:
            query = query.where(Document.title.ilike(f"%{search}%"))
        total = await self._session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        result = await self._session.execute(
            query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def create_document(
        self,
        *,
        title: str,
        source_uri: str,
        source_type: str,
        metadata: dict[str, Any],
        created_by_id: uuid.UUID,
    ) -> Document:
        document = Document(
            title=title,
            source_uri=source_uri,
            source_type=source_type,
            doc_metadata=metadata,
            created_by_id=created_by_id,
            status=DocumentStatus.PROCESSING,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def add_version(
        self,
        *,
        document_id: uuid.UUID,
        version_number: int,
        content_hash: str,
        content: str,
    ) -> DocumentVersion:
        await self._session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .values(is_current=False)
        )
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            content_hash=content_hash,
            content=content,
            is_current=True,
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def list_recent_versions(
        self, *, limit: int, offset: int
    ) -> tuple[list[tuple[DocumentVersion, str]], int]:
        """Version history across the whole corpus, newest first, with each
        version's document title (the /knowledge/versions feed)."""
        base = select(DocumentVersion, Document.title).join(
            Document, DocumentVersion.document_id == Document.id
        )
        total = await self._session.scalar(
            select(func.count()).select_from(select(DocumentVersion).subquery())
        )
        result = await self._session.execute(
            # version_number breaks created_at ties (two versions of the same
            # document can land in the same millisecond); without a total
            # order, pagination can repeat or skip rows between pages.
            base.order_by(
                DocumentVersion.created_at.desc(), DocumentVersion.version_number.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        return [(version, title) for version, title in result.all()], int(total or 0)

    async def count_documents(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(Document)) or 0)

    async def count_versions(self) -> int:
        return int(
            await self._session.scalar(select(func.count()).select_from(DocumentVersion)) or 0
        )

    async def status_counts(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Document.status, func.count()).group_by(Document.status)
        )
        return {
            (status.value if hasattr(status, "value") else str(status)): int(count)
            for status, count in result.all()
        }

    async def get_versions(self, document_id: uuid.UUID) -> list[DocumentVersion]:
        result = await self._session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number)
        )
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.flush()
