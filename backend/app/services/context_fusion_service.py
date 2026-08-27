"""Context fusion service (Module 7).

Retrieval candidates (already fused across BM25/vector/graph by RRF in
Module 6) -> duplicate removal -> cross-encoder reranking -> Phase 13
conflict resolution (drop the losing side of any precomputed
cross-document contradiction among today's candidates, or flag it if
authority couldn't decide) -> compression to the final top-K -> SOURCE-N
context blocks for the generator.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.context_fusion.builder import ContextBlock, build_context_blocks, build_context_text
from app.modules.context_fusion.compressor import compress_to_top_k
from app.modules.context_fusion.conflict_resolution import (
    ConflictNote,
    ConflictRecord,
    resolve_conflicts,
)
from app.modules.context_fusion.dedup import deduplicate
from app.modules.context_fusion.reranker import Reranker
from app.modules.context_fusion.types import EvidenceChunk
from app.repositories.conflict_repository import ConflictRepository
from app.services.retrieval_service import RetrievedItem

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ContextFusionResult:
    """``items`` and ``blocks`` are the same final set, same order —
    ``items`` carries full provenance (chunk/document ids, retrievers,
    scores) for persistence, ``blocks`` is the minimal shape the
    generator needs to build the SOURCE-N prompt.
    """

    items: list[EvidenceChunk]
    blocks: list[ContextBlock]
    context_text: str
    candidates_in: int
    after_dedup: int
    final_count: int
    reranker_model: str
    conflicts: list[ConflictNote]


def _to_evidence(item: RetrievedItem) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=item.item.chunk.id,
        document_id=item.item.chunk.document_id,
        document_title=item.item.document_title,
        version_number=item.item.version_number,
        page_number=item.item.chunk.page_number,
        section=item.item.chunk.section,
        content=item.item.chunk.content,
        retrieval_score=item.score,
        retrievers=item.retrievers,
    )


class ContextFusionService:
    def __init__(
        self, settings: Settings, reranker: Reranker, conflict_repository: ConflictRepository
    ) -> None:
        self._settings = settings
        self._reranker = reranker
        self._conflicts = conflict_repository

    async def fuse(
        self, query: str, candidates: list[RetrievedItem], top_k: int
    ) -> ContextFusionResult:
        evidence = [_to_evidence(item) for item in candidates]

        deduped = deduplicate(evidence)
        reranked = await self._reranker.rerank(query, deduped)

        conflict_records = await self._load_conflicts(reranked)
        resolved, conflict_notes = resolve_conflicts(reranked, conflict_records)

        compressed = compress_to_top_k(resolved, top_k)

        blocks = build_context_blocks(compressed)
        context_text = build_context_text(blocks)

        logger.info(
            "context_fused",
            candidates=len(evidence),
            after_dedup=len(deduped),
            final=len(blocks),
            reranker=self._reranker.model_name,
            conflicts=len(conflict_notes),
        )
        return ContextFusionResult(
            items=compressed,
            blocks=blocks,
            context_text=context_text,
            candidates_in=len(evidence),
            after_dedup=len(deduped),
            final_count=len(blocks),
            reranker_model=self._reranker.model_name,
            conflicts=conflict_notes,
        )

    async def _load_conflicts(self, items: list[EvidenceChunk]) -> list[ConflictRecord]:
        chunk_ids = [item.chunk_id for item in items]
        rows = await self._conflicts.find_among_chunk_ids(chunk_ids)
        return [
            ConflictRecord(
                claim_a_chunk_id=row.claim_a_chunk_id,
                claim_b_chunk_id=row.claim_b_chunk_id,
                contradiction_score=row.contradiction_score,
                preferred_chunk_id=row.preferred_chunk_id,
                resolved=row.resolved,
                resolution_reason=row.resolution_reason,
            )
            for row in rows
        ]
