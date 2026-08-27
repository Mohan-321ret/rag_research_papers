"""Cross-document knowledge conflict detection (Phase 13).

    Claim A  <->  Contradiction  <->  Claim B

For every chunk in a newly processed document, search the *rest* of the
corpus (every other document's current content) for semantically similar
claims, and check each for contradiction via NLI. A hit gets resolved by
metadata (priority -> date -> version; see authority_resolver) and
persisted — Context Fusion later looks these up (cheaply, no live NLI)
when deciding what to hand the generator.

Runs best-effort from ``ProcessingService`` alongside evolution analysis:
a failure here must never fail the upload/process request.
"""

import uuid

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.conflict import KnowledgeConflict
from app.modules.conflict.authority_resolver import DocumentAuthority, resolve_authority
from app.modules.processing.embedding import SentenceTransformerEmbedder
from app.modules.repository.vector_store import get_vector_store
from app.modules.verification.nli_verifier import NliVerifier, nli_available
from app.repositories.chunk_repository import ChunkRepository, ConflictCandidate
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.document_repository import DocumentRepository

logger = get_logger(__name__)

_CANDIDATES_PER_CHUNK = 5


class ConflictService:
    def __init__(
        self,
        settings: Settings,
        conflict_repository: ConflictRepository,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        embedder: SentenceTransformerEmbedder,
        verifier: NliVerifier,
    ) -> None:
        self._settings = settings
        self._conflicts = conflict_repository
        self._documents = document_repository
        self._chunks = chunk_repository
        self._embedder = embedder
        self._verifier = verifier

    async def detect_for_document(
        self, document_id: uuid.UUID, new_chunks: list[tuple[uuid.UUID, str]]
    ) -> list[KnowledgeConflict]:
        if not (self._settings.conflict_detection_enabled and nli_available()):
            return []
        if not new_chunks:
            return []

        document = await self._documents.get(document_id)
        if document is None:
            return []
        versions = await self._documents.get_versions(document_id)
        current_version = next((v for v in versions if v.is_current), None)
        if current_version is None:
            return []

        own_priority = int(document.doc_metadata.get("priority") or 0)
        own_department = document.doc_metadata.get("department")

        detected: list[KnowledgeConflict] = []
        for chunk_id, content in new_chunks:
            candidates = await self._search_candidates(content, exclude_document_id=document_id)
            for candidate in candidates:
                score = await self._contradiction_score(content, candidate.chunk.content)
                if score < self._settings.conflict_contradiction_threshold:
                    continue

                claim_a = DocumentAuthority(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    document_title=document.title,
                    department=own_department,
                    priority=own_priority,
                    version_number=current_version.version_number,
                    version_created_at=current_version.created_at,
                )
                claim_b = DocumentAuthority(
                    document_id=candidate.document_id,
                    chunk_id=candidate.chunk.id,
                    document_title=candidate.document_title,
                    department=candidate.department,
                    priority=candidate.priority,
                    version_number=candidate.version_number,
                    version_created_at=candidate.version_created_at,
                )
                resolution = resolve_authority(claim_a, claim_b)

                record = await self._conflicts.create_conflict(
                    claim_a_chunk_id=chunk_id,
                    claim_a_document_id=document_id,
                    claim_a_content=content,
                    claim_b_chunk_id=candidate.chunk.id,
                    claim_b_document_id=candidate.document_id,
                    claim_b_content=candidate.chunk.content,
                    contradiction_score=round(score, 4),
                    preferred_chunk_id=resolution.preferred_chunk_id,
                    resolved=resolution.resolved,
                    resolution_reason=resolution.reason,
                )
                detected.append(record)
                logger.info(
                    "knowledge_conflict_detected",
                    document_id=str(document_id),
                    other_document_id=str(candidate.document_id),
                    contradiction_score=score,
                    resolved=resolution.resolved,
                    reason=resolution.reason,
                )
        return detected

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[KnowledgeConflict], int]:
        return await self._conflicts.list_all(limit=limit, offset=offset)

    async def list_for_document(self, document_id: uuid.UUID) -> list[KnowledgeConflict]:
        return await self._conflicts.list_for_document(document_id)

    # ---- internals ------------------------------------------------------

    async def _search_candidates(
        self, text: str, *, exclude_document_id: uuid.UUID
    ) -> list[ConflictCandidate]:
        [vector] = await self._embedder.embed_texts([text])
        store = await get_vector_store(
            self._settings.vector_index_dir,
            self._embedder.dimension,
            self._embedder.model_name,
        )
        hits = await store.search(vector, k=_CANDIDATES_PER_CHUNK)
        qualifying = [
            h for h in hits if h.score >= self._settings.conflict_similarity_threshold
        ]
        if not qualifying:
            return []
        by_ref = await self._chunks.get_current_conflict_candidates(
            [h.chunk_id for h in qualifying], exclude_document_id=exclude_document_id
        )
        return [by_ref[h.chunk_id] for h in qualifying if h.chunk_id in by_ref]

    async def _contradiction_score(self, text_a: str, text_b: str) -> float:
        result = await self._verifier.score(text_a, text_b)
        return result.contradiction
