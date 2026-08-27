"""Data access for version comparison and concept drift records."""

import uuid
from typing import Any

from sqlalchemy import func, select

from app.models.document import Document
from app.models.evolution import ConceptDriftReport, VersionComparison
from app.repositories.base import BaseRepository


class EvolutionRepository(BaseRepository):
    async def create_comparison(
        self,
        *,
        document_id: uuid.UUID,
        from_version_id: uuid.UUID | None,
        to_version_id: uuid.UUID,
        from_version_number: int | None,
        to_version_number: int,
        change_type: str,
        text_similarity: float,
        added_count: int,
        removed_count: int,
        replaced_count: int,
        added_sentences: list[str],
        removed_sentences: list[str],
        drift_score: float,
        drift_magnitude: str,
        conflicts: list[dict[str, Any]],
        has_conflict: bool,
        vectors_added: int,
        graph_synced: bool,
        summary: str,
    ) -> VersionComparison:
        record = VersionComparison(
            document_id=document_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            from_version_number=from_version_number,
            to_version_number=to_version_number,
            change_type=change_type,
            text_similarity=text_similarity,
            added_count=added_count,
            removed_count=removed_count,
            replaced_count=replaced_count,
            added_sentences=added_sentences,
            removed_sentences=removed_sentences,
            drift_score=drift_score,
            drift_magnitude=drift_magnitude,
            conflicts=conflicts,
            has_conflict=has_conflict,
            vectors_added=vectors_added,
            graph_synced=graph_synced,
            summary=summary,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_for_document(self, document_id: uuid.UUID) -> list[VersionComparison]:
        result = await self._session.execute(
            select(VersionComparison)
            .where(VersionComparison.document_id == document_id)
            .order_by(VersionComparison.to_version_number)
        )
        return list(result.scalars().all())

    async def create_concept_drift_report(
        self,
        *,
        document_id: uuid.UUID,
        old_version_id: uuid.UUID | None,
        new_version_id: uuid.UUID,
        old_version_number: int | None,
        new_version_number: int,
        drift_score: float,
        drift_type: str,
        changed_chunks: list[dict[str, Any]],
    ) -> ConceptDriftReport:
        record = ConceptDriftReport(
            document_id=document_id,
            old_version_id=old_version_id,
            new_version_id=new_version_id,
            old_version_number=old_version_number,
            new_version_number=new_version_number,
            drift_score=drift_score,
            drift_type=drift_type,
            changed_chunks=changed_chunks,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_concept_drift_for_document(
        self, document_id: uuid.UUID
    ) -> list[ConceptDriftReport]:
        result = await self._session.execute(
            select(ConceptDriftReport)
            .where(ConceptDriftReport.document_id == document_id)
            .order_by(ConceptDriftReport.new_version_number)
        )
        return list(result.scalars().all())

    async def list_recent_drift(
        self, *, limit: int, offset: int, min_drift: float | None = None
    ) -> tuple[list[tuple[VersionComparison, str]], int]:
        """Corpus-wide drift feed (the /knowledge/drift endpoint), newest
        first, with each comparison's document title."""
        base = select(VersionComparison, Document.title).join(
            Document, VersionComparison.document_id == Document.id
        )
        if min_drift is not None:
            base = base.where(VersionComparison.drift_score >= min_drift)

        total = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        result = await self._session.execute(
            # to_version_number breaks created_at ties, so paging through the
            # feed can't repeat or skip rows (see list_recent_versions).
            base.order_by(
                VersionComparison.created_at.desc(),
                VersionComparison.to_version_number.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [(row, title) for row, title in result.all()], int(total or 0)

    async def drift_summary(self) -> dict[str, int]:
        """Counts by drift magnitude, plus how many transitions conflicted."""
        magnitudes = await self._session.execute(
            select(VersionComparison.drift_magnitude, func.count()).group_by(
                VersionComparison.drift_magnitude
            )
        )
        conflicted = await self._session.scalar(
            select(func.count())
            .select_from(VersionComparison)
            .where(VersionComparison.has_conflict.is_(True))
        )
        summary = {magnitude: int(count) for magnitude, count in magnitudes.all()}
        summary["with_conflict"] = int(conflicted or 0)
        return summary
