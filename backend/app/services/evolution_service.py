"""Knowledge evolution service (Module 3 + Phase 12 concept drift).

New/updated document -> Change Detector -> Version Comparator (Diff
Detector + whole-document Drift Detector) -> Conflict Detector -> a
persisted ``VersionComparison`` row, plus chunk-level Concept Drift
Detection -> a persisted ``ConceptDriftReport``. Version Management (old
versions are never deleted, ``is_current`` tracks the active one) and
Incremental Re-indexing (new vectors added, old ones untouched; graph
re-synced) already happen in ``ProcessingService`` — this service records
*what changed* about that transition, not the indexing itself.

Runs best-effort from ``ProcessingService`` right after a new version is
chunked and embedded: a failure here must never fail the upload/process
request, only skip the evolution record for that version.
"""

import dataclasses
import uuid

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.document import DocumentVersion
from app.models.evolution import ConceptDriftReport, VersionComparison
from app.modules.evolution.change_detector import detect_change
from app.modules.evolution.concept_drift_detector import (
    ConceptDriftResult,
    detect_concept_drift,
)
from app.modules.evolution.conflict_detector import Conflict, detect_conflicts
from app.modules.evolution.diff_detector import DiffResult, compute_diff
from app.modules.evolution.drift_detector import DriftResult, detect_drift
from app.modules.processing.embedding import SentenceTransformerEmbedder, embedding_stack_available
from app.modules.verification.nli_verifier import NliVerifier, nli_available
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.evolution_repository import EvolutionRepository

logger = get_logger(__name__)


class EvolutionService:
    def __init__(
        self,
        settings: Settings,
        evolution_repository: EvolutionRepository,
        chunk_repository: ChunkRepository,
        embedder: SentenceTransformerEmbedder,
        verifier: NliVerifier,
    ) -> None:
        self._settings = settings
        self._evolution = evolution_repository
        self._chunks = chunk_repository
        self._embedder = embedder
        self._verifier = verifier

    async def analyze_version_change(
        self,
        *,
        document_id: uuid.UUID,
        previous_version: DocumentVersion | None,
        new_version: DocumentVersion,
        new_chunks: list[tuple[uuid.UUID, str]],
        vectors_added: int,
        graph_synced: bool,
    ) -> VersionComparison | None:
        if not self._settings.evolution_enabled:
            return None

        new_chunk_contents = [content for _, content in new_chunks]
        old_chunks: list[tuple[uuid.UUID, str]] = []
        if previous_version is not None:
            old_chunks = await self._chunks.list_id_content_by_version(previous_version.id)

        change = detect_change(
            previous_version.content_hash if previous_version else None,
            new_version.content_hash,
        )
        diff = compute_diff(
            previous_version.content if previous_version else None,
            new_version.content or "",
        )
        drift = await self._detect_drift(previous_version, old_chunks, new_chunk_contents, new_version)
        conflicts = await self._detect_conflicts(diff)

        summary = self._summarize(change.is_new_document, diff, drift, conflicts)
        record = await self._evolution.create_comparison(
            document_id=document_id,
            from_version_id=previous_version.id if previous_version else None,
            to_version_id=new_version.id,
            from_version_number=(
                previous_version.version_number if previous_version else None
            ),
            to_version_number=new_version.version_number,
            change_type="created" if change.is_new_document else "revised",
            text_similarity=diff.similarity_ratio,
            added_count=len(diff.added),
            removed_count=len(diff.removed),
            replaced_count=len(diff.replaced_pairs),
            added_sentences=diff.added,
            removed_sentences=diff.removed,
            drift_score=drift.score,
            drift_magnitude=drift.magnitude,
            conflicts=[dataclasses.asdict(c) for c in conflicts],
            has_conflict=bool(conflicts),
            vectors_added=vectors_added,
            graph_synced=graph_synced,
            summary=summary,
        )
        logger.info(
            "version_evolution_analyzed",
            document_id=str(document_id),
            from_version=record.from_version_number,
            to_version=record.to_version_number,
            change_type=record.change_type,
            drift=record.drift_score,
            magnitude=record.drift_magnitude,
            conflicts=len(conflicts),
        )

        if previous_version is not None:
            await self._analyze_concept_drift(
                document_id=document_id,
                previous_version=previous_version,
                new_version=new_version,
                old_chunks=old_chunks,
                new_chunks=new_chunks,
            )
        return record

    async def history(self, document_id: uuid.UUID) -> list[VersionComparison]:
        return await self._evolution.list_for_document(document_id)

    async def concept_drift_history(self, document_id: uuid.UUID) -> list[ConceptDriftReport]:
        return await self._evolution.list_concept_drift_for_document(document_id)

    # ---- internals ----------------------------------------------------

    async def _detect_drift(
        self,
        previous_version: DocumentVersion | None,
        old_chunks: list[tuple[uuid.UUID, str]],
        new_chunk_contents: list[str],
        new_version: DocumentVersion,
    ) -> DriftResult:
        if not embedding_stack_available():
            # Can't measure without the embedding stack — "unknown", not a
            # false "no drift".
            return DriftResult(score=0.0, magnitude="unknown")

        old_texts = [content for _, content in old_chunks]
        if not old_texts and previous_version is not None and previous_version.content:
            old_texts = [previous_version.content]

        new_texts = new_chunk_contents or (
            [new_version.content] if new_version.content else []
        )
        return await detect_drift(self._embed, old_texts, new_texts)

    async def _analyze_concept_drift(
        self,
        *,
        document_id: uuid.UUID,
        previous_version: DocumentVersion,
        new_version: DocumentVersion,
        old_chunks: list[tuple[uuid.UUID, str]],
        new_chunks: list[tuple[uuid.UUID, str]],
    ) -> ConceptDriftReport | None:
        if not (embedding_stack_available() and nli_available()):
            return None

        str_old = [(str(chunk_id), content) for chunk_id, content in old_chunks]
        str_new = [(str(chunk_id), content) for chunk_id, content in new_chunks]
        result: ConceptDriftResult = await detect_concept_drift(
            self._embed,
            self._verifier,
            str_old,
            str_new,
            threshold=self._settings.concept_drift_threshold,
        )
        record = await self._evolution.create_concept_drift_report(
            document_id=document_id,
            old_version_id=previous_version.id,
            new_version_id=new_version.id,
            old_version_number=previous_version.version_number,
            new_version_number=new_version.version_number,
            drift_score=result.drift_score,
            drift_type=result.drift_type,
            changed_chunks=[dataclasses.asdict(c) for c in result.changed_chunks],
        )
        logger.info(
            "concept_drift_analyzed",
            document_id=str(document_id),
            from_version=previous_version.version_number,
            to_version=new_version.version_number,
            drift_score=result.drift_score,
            drift_type=result.drift_type,
            changed_chunks=len(result.changed_chunks),
        )
        return record

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = await self._embedder.embed_texts(texts)
        return [list(v) for v in vectors]

    async def _detect_conflicts(self, diff: DiffResult) -> list[Conflict]:
        if not diff.replaced_pairs:
            return []
        if not (self._settings.evolution_enabled and nli_available()):
            return []
        return await detect_conflicts(
            self._verifier, diff.replaced_pairs, self._settings.evolution_conflict_threshold
        )

    @staticmethod
    def _summarize(
        is_new_document: bool,
        diff: DiffResult,
        drift: DriftResult,
        conflicts: list[Conflict],
    ) -> str:
        if is_new_document:
            return f"New document: {len(diff.added)} sentence(s) indexed."
        parts = [
            f"{len(diff.added)} added",
            f"{len(diff.removed)} removed",
            f"{len(diff.replaced_pairs)} replaced",
            f"text similarity {diff.similarity_ratio:.2f}",
            f"semantic drift {drift.score:.2f} ({drift.magnitude})",
        ]
        if conflicts:
            parts.append(f"{len(conflicts)} conflict(s) detected")
        return ", ".join(parts) + "."
