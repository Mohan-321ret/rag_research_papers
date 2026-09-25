"""Data access for document chunks."""

import uuid
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import delete, func, select

from app.models.document import Document, DocumentChunk, DocumentVersion
from app.repositories.base import BaseRepository


class RetrievableChunk(NamedTuple):
    """A chunk joined with its document context, ready for citation."""

    chunk: DocumentChunk
    document_title: str
    version_number: int


class ConflictCandidate(NamedTuple):
    """A chunk from another document, with the metadata Phase 13's
    authority resolver needs (priority, department, version, date)."""

    chunk: DocumentChunk
    document_id: uuid.UUID
    document_title: str
    department: str | None
    priority: int
    version_number: int
    version_created_at: datetime


class ChunkRepository(BaseRepository):
    async def filter_existing_chunk_ids(self, chunk_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not chunk_ids:
            return set()
        stmt = select(DocumentChunk.id).where(DocumentChunk.id.in_(chunk_ids))
        res = await self._session.execute(stmt)
        return set(res.scalars().all())

    async def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        self._session.add_all(chunks)
        await self._session.flush()

    async def list_by_version(
        self, version_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[DocumentChunk], int]:
        base = select(DocumentChunk).where(DocumentChunk.version_id == version_id)
        total = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        result = await self._session.execute(
            base.order_by(DocumentChunk.chunk_index).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_current_by_embedding_refs(
        self, refs: list[str]
    ) -> dict[str, RetrievableChunk]:
        """Chunks for the given vector ids, restricted to current versions.

        Old versions keep their vectors for historical queries, but the
        baseline chat answers from current knowledge only.
        """
        if not refs:
            return {}
        result = await self._session.execute(
            select(DocumentChunk, Document.title, DocumentVersion.version_number)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentChunk.embedding_ref.in_(refs),
                DocumentVersion.is_current.is_(True),
            )
        )
        return {
            chunk.embedding_ref: RetrievableChunk(chunk, title, version_number)
            for chunk, title, version_number in result.all()
        }

    async def get_current_conflict_candidates(
        self, refs: list[str], exclude_document_id: uuid.UUID
    ) -> dict[str, ConflictCandidate]:
        """Current-version chunks for the given vector ids, from any
        document *other than* ``exclude_document_id`` — candidates for
        cross-document conflict detection, carrying the metadata
        (priority, department, version, date) authority resolution needs.
        """
        if not refs:
            return {}
        result = await self._session.execute(
            select(DocumentChunk, Document, DocumentVersion.version_number, DocumentVersion.created_at)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentChunk.embedding_ref.in_(refs),
                DocumentVersion.is_current.is_(True),
                Document.id != exclude_document_id,
            )
        )
        return {
            chunk.embedding_ref: ConflictCandidate(
                chunk=chunk,
                document_id=document.id,
                document_title=document.title,
                department=document.doc_metadata.get("department"),
                priority=int(document.doc_metadata.get("priority") or 0),
                version_number=version_number,
                version_created_at=version_created_at,
            )
            for chunk, document, version_number, version_created_at in result.all()
        }

    @staticmethod
    def _as_of_version_ids(as_of: datetime):
        """Subquery: each document's latest version created before
        ``as_of`` — the version that was active at that point in time."""
        ranked = (
            select(
                DocumentVersion.id.label("version_id"),
                func.row_number()
                .over(
                    partition_by=DocumentVersion.document_id,
                    order_by=DocumentVersion.created_at.desc(),
                )
                .label("rank"),
            )
            .where(DocumentVersion.created_at < as_of)
            .subquery()
        )
        return select(ranked.c.version_id).where(ranked.c.rank == 1)

    async def get_as_of_by_embedding_refs(
        self, refs: list[str], as_of: datetime
    ) -> dict[str, RetrievableChunk]:
        """Chunks for the given vector ids, restricted to each document's
        *as-of* version: the latest version created before ``as_of`` — the
        one that was active at that point in time, current or not.

        A document with no version that old (it didn't exist yet as of
        that date) contributes nothing.
        """
        if not refs:
            return {}
        result = await self._session.execute(
            select(DocumentChunk, Document.title, DocumentVersion.version_number)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentChunk.embedding_ref.in_(refs),
                DocumentVersion.id.in_(self._as_of_version_ids(as_of)),
            )
        )
        return {
            chunk.embedding_ref: RetrievableChunk(chunk, title, version_number)
            for chunk, title, version_number in result.all()
        }

    async def get_current_by_ids(
        self, chunk_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, RetrievableChunk]:
        """Current-version chunks by primary key (BM25/graph hydration)."""
        if not chunk_ids:
            return {}
        result = await self._session.execute(
            select(DocumentChunk, Document.title, DocumentVersion.version_number)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                DocumentVersion.is_current.is_(True),
            )
        )
        return {
            chunk.id: RetrievableChunk(chunk, title, version_number)
            for chunk, title, version_number in result.all()
        }

    async def get_as_of_by_ids(
        self, chunk_ids: list[uuid.UUID], as_of: datetime
    ) -> dict[uuid.UUID, RetrievableChunk]:
        """As ``get_current_by_ids``, but restricted to each document's
        as-of version rather than its current one. A chunk whose own
        version isn't the as-of version for its document (e.g. a current
        chunk found by BM25, which only ever searches current content)
        resolves to nothing here — it simply isn't valid as of that date.
        """
        if not chunk_ids:
            return {}
        result = await self._session.execute(
            select(DocumentChunk, Document.title, DocumentVersion.version_number)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                DocumentVersion.id.in_(self._as_of_version_ids(as_of)),
            )
        )
        return {
            chunk.id: RetrievableChunk(chunk, title, version_number)
            for chunk, title, version_number in result.all()
        }

    async def corpus_fingerprint(self) -> tuple[int, str]:
        """Cheap staleness signal for the BM25 index (count + newest id)."""
        count = await self._session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .where(DocumentVersion.is_current.is_(True))
        )
        newest = await self._session.execute(
            select(DocumentChunk.id)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .where(DocumentVersion.is_current.is_(True))
            .order_by(DocumentChunk.created_at.desc(), DocumentChunk.id.desc())
            .limit(1)
        )
        newest_id = newest.scalar_one_or_none()
        return (int(count or 0), str(newest_id) if newest_id else "")

    async def list_current_corpus(self) -> list[tuple[uuid.UUID, str]]:
        """(chunk_id, content) for all current-version chunks (BM25 build)."""
        result = await self._session.execute(
            select(DocumentChunk.id, DocumentChunk.content)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .where(DocumentVersion.is_current.is_(True))
        )
        return [(chunk_id, content) for chunk_id, content in result.all()]

    async def get_by_embedding_refs(self, refs: list[str]) -> list[DocumentChunk]:
        if not refs:
            return []
        result = await self._session.execute(
            select(DocumentChunk).where(DocumentChunk.embedding_ref.in_(refs))
        )
        return list(result.scalars().all())

    async def embedding_refs_for_version(self, version_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(DocumentChunk.embedding_ref).where(
                DocumentChunk.version_id == version_id,
                DocumentChunk.embedding_ref.is_not(None),
            )
        )
        return [ref for (ref,) in result.all()]

    async def list_contents_by_version(self, version_id: uuid.UUID) -> list[str]:
        """Chunk text of one version, in order (for drift centroid embedding)."""
        result = await self._session.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.version_id == version_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return [content for (content,) in result.all()]

    async def list_id_content_by_version(
        self, version_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """(chunk_id, content) pairs for one version, in order — for
        chunk-level concept drift, which needs to reference specific
        chunks, not just their text."""
        result = await self._session.execute(
            select(DocumentChunk.id, DocumentChunk.content)
            .where(DocumentChunk.version_id == version_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return [(chunk_id, content) for chunk_id, content in result.all()]

    async def list_for_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        """All chunks of all versions of a document (for graph sync)."""
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.version_id, DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def embedding_refs_for_document(self, document_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(DocumentChunk.embedding_ref).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding_ref.is_not(None),
            )
        )
        return [ref for (ref,) in result.all()]

    async def list_rows_by_version(self, version_id: uuid.UUID) -> list[DocumentChunk]:
        """All chunk rows of one version, in order — the input to
        incremental re-index planning (needs content, embedding_ref and
        metadata, and the rows themselves so unchanged ones can be kept
        and repositioned in place)."""
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.version_id == version_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def delete_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Delete specific chunk rows (the obsolete ones), leaving the
        rest of the version's rows untouched."""
        for chunk in chunks:
            await self._session.delete(chunk)
        await self._session.flush()

    async def delete_by_version(self, version_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.version_id == version_id)
        )

    def make_chunk(
        self,
        *,
        version_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_index: int,
        content: str,
        token_count: int,
        page_number: int | None,
        section: str | None,
        embedding_ref: str,
        metadata: dict[str, Any],
    ) -> DocumentChunk:
        return DocumentChunk(
            version_id=version_id,
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            token_count=token_count,
            page_number=page_number,
            section=section,
            embedding_ref=embedding_ref,
            chunk_metadata=metadata,
        )
