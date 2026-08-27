"""Document processing service.

Turns an extracted document version into searchable knowledge:
cleaning -> noise removal -> language detection -> semantic chunking ->
embedding generation -> PostgreSQL (chunk rows) + FAISS (vectors).

Re-indexing is **incremental** (Phase 14): rather than dropping the index
and re-embedding everything whenever a document changes, each run diffs
the freshly produced chunks against what is already stored and pays the
transformer cost only for chunks that actually changed. Unchanged chunks
either keep their row and vector outright (re-running the same version)
or copy the stored vector to the new version's row. Vectors of *old*
versions are never retired — they back historical answers.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.modules.processing.chunking import SemanticChunker
from app.modules.processing.cleaning import clean_text
from app.modules.processing.embedding import SentenceTransformerEmbedder
from app.modules.processing.entities import extract_entities, extract_topics
from app.modules.processing.incremental import (
    ExistingChunk,
    PlannedChunk,
    ReindexPlan,
    plan_reindex,
)
from app.modules.processing.language import detect_language
from app.modules.repository.vector_store import (
    get_existing_vector_store,
    get_vector_store,
)
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.processing import ChunkListResponse, ChunkRead, ProcessingResult
from app.services.conflict_service import ConflictService
from app.services.evolution_service import EvolutionService
from app.services.graph_service import GraphService

logger = get_logger(__name__)

_ENTITIES_PER_CHUNK = 8
# Kept rows are parked above any realistic chunk_index while indices are
# permuted, so the (version_id, chunk_index) unique constraint can't trip
# mid-update.
_INDEX_PARK_BASE = 1_000_000


class ProcessingService:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        embedder: SentenceTransformerEmbedder,
        knowledge_repository: KnowledgeRepository | None = None,
        graph_service: GraphService | None = None,
        evolution_service: EvolutionService | None = None,
        conflict_service: ConflictService | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        self._documents = document_repository
        self._chunks = chunk_repository
        self._embedder = embedder
        self._knowledge = knowledge_repository
        self._graph = graph_service
        self._evolution = evolution_service
        self._conflicts = conflict_service
        self._chunker = SemanticChunker(
            target_tokens=settings.chunk_target_tokens,
            overlap_sentences=settings.chunk_overlap_sentences,
        )

    async def process_document(self, document_id: uuid.UUID) -> ProcessingResult:
        """Run the full pipeline on the document's current version."""
        document = await self._documents.get(document_id)
        if document is None:
            raise NotFoundError("Document not found")
        # Query versions explicitly: on a document created earlier in this
        # request the relationship is unloaded, and lazy loading is
        # unavailable in async context.
        versions = await self._documents.get_versions(document_id)
        version = next((v for v in versions if v.is_current), None)
        if version is None:
            raise ConflictError("Document has no current version to process")
        if not (version.content or "").strip():
            raise ConflictError("Document version has no extracted text to process")

        document.status = DocumentStatus.PROCESSING
        try:
            result = await self._run_pipeline(document, version)
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.doc_metadata = {
                **document.doc_metadata,
                "processing_error": f"{type(exc).__name__}: {exc}",
            }
            await self._session.commit()
            logger.exception("document_processing_failed", document_id=str(document_id))
            raise
        await self._session.commit()
        await self._sync_graph_best_effort(document, version)
        await self._analyze_evolution_best_effort(document, version, versions, result)
        await self._detect_conflicts_best_effort(document, version)
        return result

    async def _analyze_evolution_best_effort(
        self,
        document: Document,
        version: DocumentVersion,
        versions: list[DocumentVersion],
        result: ProcessingResult,
    ) -> None:
        """Module 3: record what changed about this version transition;
        degrade gracefully (skip, don't fail the request) on any error."""
        if self._evolution is None:
            return
        previous_version = next(
            (v for v in versions if v.version_number == version.version_number - 1),
            None,
        )
        try:
            new_chunks = await self._chunks.list_id_content_by_version(version.id)
            await self._evolution.analyze_version_change(
                document_id=document.id,
                previous_version=previous_version,
                new_version=version,
                new_chunks=new_chunks,
                vectors_added=result.vectors_added,
                graph_synced=bool(document.doc_metadata.get("graph_synced")),
            )
            await self._session.commit()
        except Exception as exc:
            logger.warning(
                "evolution_analysis_failed",
                document_id=str(document.id),
                error=type(exc).__name__,
            )

    async def _detect_conflicts_best_effort(
        self, document: Document, version: DocumentVersion
    ) -> None:
        """Phase 13: check this version's chunks against the rest of the
        corpus for cross-document contradictions; degrade gracefully
        (skip, don't fail the request) on any error."""
        if self._conflicts is None:
            return
        try:
            new_chunks = await self._chunks.list_id_content_by_version(version.id)
            await self._conflicts.detect_for_document(document.id, new_chunks)
            await self._session.commit()
        except Exception as exc:
            logger.warning(
                "conflict_detection_failed",
                document_id=str(document.id),
                error=type(exc).__name__,
            )

    async def _sync_graph_best_effort(
        self, document: Document, version: DocumentVersion
    ) -> None:
        """Mirror the document into Neo4j; degrade gracefully if it's down.

        Only the version just processed is sent: every other version's
        nodes are already in the graph and unchanged, so re-sending them
        would be the graph equivalent of rebuilding the whole index.
        """
        if self._graph is None or not self._settings.graph_auto_sync:
            return
        try:
            only = version.id if self._settings.incremental_reindex_enabled else None
            await self._graph.sync_document(document.id, only_version_id=only)
            synced = True
        except Exception as exc:
            synced = False
            logger.warning(
                "graph_sync_failed",
                document_id=str(document.id),
                error=type(exc).__name__,
            )
        document.doc_metadata = {**document.doc_metadata, "graph_synced": synced}
        await self._session.commit()

    async def _previous_version(
        self, document_id: uuid.UUID, version: DocumentVersion
    ) -> DocumentVersion | None:
        versions = await self._documents.get_versions(document_id)
        return next(
            (v for v in versions if v.version_number == version.version_number - 1), None
        )

    def _to_existing(self, row: DocumentChunk) -> ExistingChunk:
        """Reuse view of a stored chunk.

        A vector produced by a *different* embedding model isn't
        interchangeable with one from the current model, so such a chunk is
        never offered for reuse — it gets re-embedded instead (and, when
        re-running the same version, retired as obsolete).
        """
        metadata = row.chunk_metadata or {}
        same_model = metadata.get("embedding_model") == self._embedder.model_name
        return ExistingChunk(
            chunk_id=row.id,
            content=row.content,
            embedding_ref=row.embedding_ref if (same_model and row.embedding_ref) else None,
            chunk_index=row.chunk_index,
        )

    def _plan(self, drafts: list, source_rows: list[DocumentChunk]) -> ReindexPlan:
        existing = [self._to_existing(row) for row in source_rows]
        if self._settings.incremental_reindex_enabled:
            return plan_reindex(drafts, existing)
        # Ablation baseline for the paper: the naive rebuild — nothing is
        # reused, every chunk is embedded again.
        return ReindexPlan(
            planned=[PlannedChunk(draft=draft, reuse_from=None) for draft in drafts],
            obsolete=existing,
        )

    async def _run_pipeline(
        self, document: Document, version: DocumentVersion
    ) -> ProcessingResult:
        cleaned = clean_text(version.content or "")
        language = detect_language(cleaned.text)
        drafts = self._chunker.split(cleaned.text)
        if not drafts:
            raise ConflictError("No chunks could be produced from this document")

        # The vector store is opened before any embedding happens now (a
        # fully-reused run may never call the model at all), so the model
        # has to be loaded explicitly for its dimension to be known.
        # Idempotent and lock-guarded — a no-op once loaded.
        await self._embedder.load()
        store = await get_vector_store(
            self._settings.vector_index_dir,
            self._embedder.dimension,
            self._embedder.model_name,
        )

        # What this run can reuse. Re-running the *same* version compares
        # against its own rows (unchanged ones are kept outright, vectors
        # untouched); a *new* version compares against its predecessor —
        # new rows are required, but an unchanged chunk's stored vector can
        # be copied instead of recomputed.
        own_rows = await self._chunks.list_rows_by_version(version.id)
        reprocessing = bool(own_rows)
        if reprocessing:
            source_rows = own_rows
        else:
            previous = await self._previous_version(document.id, version)
            source_rows = (
                await self._chunks.list_rows_by_version(previous.id) if previous else []
            )

        rows_by_id = {row.id: row for row in source_rows}
        plan = self._plan(drafts, source_rows)
        # Only a re-run of *this* version may retire rows and vectors. A new
        # version never touches its predecessor's: those back historical
        # ("what was the policy in 2023?") retrieval.
        obsolete = plan.obsolete if reprocessing else []

        keep: list[tuple[PlannedChunk, DocumentChunk]] = []
        needs_vector: list[PlannedChunk] = []
        recovered: dict[int, list[float]] = {}
        if reprocessing:
            for entry in plan.planned:
                if entry.reuse_from is not None:
                    keep.append((entry, rows_by_id[entry.reuse_from.chunk_id]))
                else:
                    needs_vector.append(entry)
        else:
            needs_vector = list(plan.planned)
            refs = [
                int(entry.reuse_from.embedding_ref)
                for entry in plan.reused
                if entry.reuse_from.embedding_ref is not None
            ]
            recovered = await store.reconstruct(refs)

        # The point of this phase: embed only what couldn't be reused. A
        # reusable chunk whose vector has gone missing from the index falls
        # back to being embedded rather than failing the run.
        reusable_vectors: list[list[float] | None] = []
        to_embed: list[PlannedChunk] = []
        for entry in needs_vector:
            vector = None
            if entry.reuse_from is not None and entry.reuse_from.embedding_ref is not None:
                vector = recovered.get(int(entry.reuse_from.embedding_ref))
            reusable_vectors.append(vector)
            if vector is None:
                to_embed.append(entry)

        fresh = (
            await self._embedder.embed_texts([entry.draft.content for entry in to_embed])
            if to_embed
            else []
        )
        fresh_iter = iter(fresh)
        vectors = [
            list(vector) if vector is not None else list(next(fresh_iter))
            for vector in reusable_vectors
        ]
        vector_ids = await store.add(vectors) if vectors else []

        vectors_removed = 0
        if obsolete:
            obsolete_rows = [rows_by_id[chunk.chunk_id] for chunk in obsolete]
            # Read the live refs off the rows (the reuse view nulls them for
            # foreign-model vectors, which still need retiring).
            stale_refs = [int(row.embedding_ref) for row in obsolete_rows if row.embedding_ref]
            await self._chunks.delete_chunks(obsolete_rows)
            if stale_refs:
                await store.remove(stale_refs)
                vectors_removed = len(stale_refs)

        if keep:
            # Park kept rows outside the final index range first: indices
            # permute when a chunk is inserted or removed above them, and
            # (version_id, chunk_index) is unique.
            for offset, (_, row) in enumerate(keep):
                row.chunk_index = _INDEX_PARK_BASE + offset
            await self._session.flush()
            for entry, row in keep:
                row.chunk_index = entry.draft.chunk_index
                row.page_number = entry.draft.page_number
                row.section = entry.draft.section
                row.token_count = entry.draft.token_estimate
            await self._session.flush()

        new_rows: list[DocumentChunk] = []
        for entry, vector_id in zip(needs_vector, vector_ids):
            source = (
                rows_by_id.get(entry.reuse_from.chunk_id)
                if entry.reuse_from is not None
                else None
            )
            if source is not None:
                # Byte-identical content -> identical entities; skip
                # re-extraction too, not just re-embedding.
                metadata = dict(source.chunk_metadata or {})
            else:
                metadata = {
                    "entities": [
                        {"name": e.name, "entity_type": e.entity_type}
                        for e in extract_entities(
                            entry.draft.content, max_entities=_ENTITIES_PER_CHUNK
                        )
                    ]
                }
            metadata["language"] = language.language
            metadata["embedding_model"] = self._embedder.model_name
            new_rows.append(
                self._chunks.make_chunk(
                    version_id=version.id,
                    document_id=document.id,
                    chunk_index=entry.draft.chunk_index,
                    content=entry.draft.content,
                    token_count=entry.draft.token_estimate,
                    page_number=entry.draft.page_number,
                    section=entry.draft.section,
                    embedding_ref=str(vector_id),
                    metadata=metadata,
                )
            )
        if new_rows:
            await self._chunks.add_chunks(new_rows)

        final_rows = [row for _, row in keep] + new_rows
        topics = extract_topics(cleaned.text)
        if self._knowledge is not None:
            unique_entities = list(
                {
                    (entity["name"], entity["entity_type"])
                    for row in final_rows
                    for entity in (row.chunk_metadata or {}).get("entities", [])
                }
            )
            await self._knowledge.replace_document_entities(document.id, unique_entities)

        document.status = DocumentStatus.READY
        document.doc_metadata = {
            **{k: v for k, v in document.doc_metadata.items() if k != "processing_error"},
            "language": language.language,
            "language_confidence": language.confidence,
            "chunk_count": len(final_rows),
            "embedding_model": self._embedder.model_name,
            "noise_lines_removed": cleaned.noise_lines_removed,
            "topics": topics,
        }

        logger.info(
            "document_processed",
            document_id=str(document.id),
            version=version.version_number,
            chunks=len(final_rows),
            embedded=len(to_embed),
            reused=len(drafts) - len(to_embed),
            vectors_added=len(vector_ids),
            vectors_removed=vectors_removed,
            incremental=self._settings.incremental_reindex_enabled,
            language=language.language,
            backend=type(store).__name__,
        )
        return ProcessingResult(
            document_id=document.id,
            version_id=version.id,
            version_number=version.version_number,
            status=DocumentStatus.READY.value,
            language=language.language,
            language_confidence=language.confidence,
            chunk_count=len(final_rows),
            embedded_count=len(to_embed),
            chunks_reused=len(drafts) - len(to_embed),
            vectors_added=len(vector_ids),
            vectors_removed=vectors_removed,
            incremental=self._settings.incremental_reindex_enabled,
            noise_lines_removed=cleaned.noise_lines_removed,
            embedding_model=self._embedder.model_name,
            vector_backend=type(store).__name__,
        )

    async def list_chunks(
        self,
        document_id: uuid.UUID,
        *,
        version_number: int | None,
        limit: int,
        offset: int,
    ) -> ChunkListResponse:
        document = await self._documents.get(document_id)
        if document is None:
            raise NotFoundError("Document not found")
        versions = await self._documents.get_versions(document_id)
        if version_number is None:
            version = next((v for v in versions if v.is_current), None)
        else:
            version = next(
                (v for v in versions if v.version_number == version_number), None
            )
        if version is None:
            raise NotFoundError("Document version not found")

        chunks, total = await self._chunks.list_by_version(
            version.id, limit=limit, offset=offset
        )
        return ChunkListResponse(
            items=[ChunkRead.model_validate(c) for c in chunks],
            total=total,
            limit=limit,
            offset=offset,
            version_id=version.id,
            version_number=version.version_number,
        )

    async def remove_document_from_graph(self, document_id: uuid.UUID) -> None:
        """Best-effort removal of the document's graph projection."""
        if self._graph is None:
            return
        try:
            await self._graph.delete_document(document_id)
        except Exception as exc:
            logger.warning(
                "graph_delete_failed",
                document_id=str(document_id),
                error=type(exc).__name__,
            )

    async def remove_document_vectors(self, document_id: uuid.UUID) -> None:
        """Remove all of a document's vectors (called before deletion)."""
        refs = await self._chunks.embedding_refs_for_document(document_id)
        if not refs:
            return
        store = await get_existing_vector_store(self._settings.vector_index_dir)
        if store is not None:
            await store.remove([int(ref) for ref in refs])


def processing_unavailable_error() -> ServiceUnavailableError:
    return ServiceUnavailableError(
        "Document processing is unavailable: the embedding stack "
        "(sentence-transformers) is not installed in this environment"
    )
