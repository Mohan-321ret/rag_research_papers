"""Data access for cross-document knowledge conflicts (Phase 13)."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select

from app.models.conflict import KnowledgeConflict
from app.repositories.base import BaseRepository


class ConflictRepository(BaseRepository):
    async def create_conflict(
        self,
        *,
        claim_a_chunk_id: uuid.UUID,
        claim_a_document_id: uuid.UUID,
        claim_a_content: str,
        claim_b_chunk_id: uuid.UUID,
        claim_b_document_id: uuid.UUID,
        claim_b_content: str,
        contradiction_score: float,
        preferred_chunk_id: uuid.UUID | None,
        resolved: bool,
        resolution_reason: str,
    ) -> KnowledgeConflict:
        record = KnowledgeConflict(
            claim_a_chunk_id=claim_a_chunk_id,
            claim_a_document_id=claim_a_document_id,
            claim_a_content=claim_a_content,
            claim_b_chunk_id=claim_b_chunk_id,
            claim_b_document_id=claim_b_document_id,
            claim_b_content=claim_b_content,
            contradiction_score=contradiction_score,
            preferred_chunk_id=preferred_chunk_id,
            resolved=resolved,
            resolution_reason=resolution_reason,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_all(
        self, *, limit: int, offset: int
    ) -> tuple[list[KnowledgeConflict], int]:
        total = await self._session.scalar(select(func.count()).select_from(KnowledgeConflict))
        result = await self._session.execute(
            select(KnowledgeConflict)
            .order_by(KnowledgeConflict.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def list_for_document(self, document_id: uuid.UUID) -> list[KnowledgeConflict]:
        result = await self._session.execute(
            select(KnowledgeConflict)
            .where(
                (KnowledgeConflict.claim_a_document_id == document_id)
                | (KnowledgeConflict.claim_b_document_id == document_id)
            )
            .order_by(KnowledgeConflict.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_among_chunk_ids(
        self, chunk_ids: Iterable[uuid.UUID]
    ) -> list[KnowledgeConflict]:
        """Precomputed conflicts where *both* sides are in this set — used
        by Context Fusion to resolve conflicts among today's retrieval
        candidates without any live NLI computation on the query path."""
        ids = list(chunk_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(KnowledgeConflict).where(
                KnowledgeConflict.claim_a_chunk_id.in_(ids),
                KnowledgeConflict.claim_b_chunk_id.in_(ids),
            )
        )
        return list(result.scalars().all())
