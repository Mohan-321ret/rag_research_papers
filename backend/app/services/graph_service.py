"""Knowledge graph service: mirrors PostgreSQL state into Neo4j.

PostgreSQL remains the source of truth; the graph is a projection built
from documents, versions, chunks and their extracted entities/topics.
Sync is idempotent, so it can be re-run at any time.
"""

import uuid

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.modules.repository.graph_store import GraphStore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.graph import DocumentGraph, GraphStats, GraphSyncResult

logger = get_logger(__name__)


class GraphService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        graph_store: GraphStore,
    ) -> None:
        self._documents = document_repository
        self._chunks = chunk_repository
        self._graph = graph_store

    async def sync_document(
        self, document_id: uuid.UUID, *, only_version_id: uuid.UUID | None = None
    ) -> GraphSyncResult:
        """Mirror a document into the graph.

        ``only_version_id`` narrows the chunk payload to a single version —
        the incremental path used after processing, where every other
        version's nodes are already in the graph and unchanged. The full
        version list is still sent (it's a handful of rows, and the
        SUPERSEDES chain needs it); all writes are idempotent MERGEs, so a
        partial payload converges to the same graph.
        """
        document = await self._documents.get(document_id)
        if document is None:
            raise NotFoundError("Document not found")

        versions = await self._documents.get_versions(document_id)
        chunks = await self._chunks.list_for_document(document_id)
        if only_version_id is not None:
            chunks = [c for c in chunks if c.version_id == only_version_id]
        metadata = document.doc_metadata

        payload = {
            "document": {
                "id": str(document.id),
                "title": document.title,
                "status": document.status.value,
                "source_type": document.source_type,
            },
            "author": metadata.get("author"),
            "department": metadata.get("department"),
            "topics": metadata.get("topics", []),
            "versions": [
                {
                    "id": str(v.id),
                    "version_number": v.version_number,
                    "content_hash": v.content_hash,
                    "is_current": v.is_current,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
            "chunks": [
                {
                    "id": str(c.id),
                    "version_id": str(c.version_id),
                    "chunk_index": c.chunk_index,
                    "section": c.section,
                    "page_number": c.page_number,
                    "entities": c.chunk_metadata.get("entities", []),
                }
                for c in chunks
            ],
        }
        counts = await self._graph.sync_document(payload)
        logger.info(
            "graph_synced",
            document_id=str(document_id),
            chunks_sent=len(chunks),
            incremental=only_version_id is not None,
            **counts,
        )
        return GraphSyncResult(document_id=document_id, **counts)

    async def delete_document(self, document_id: uuid.UUID) -> None:
        await self._graph.delete_document(str(document_id))

    async def stats(self) -> GraphStats:
        return GraphStats(**await self._graph.stats())

    async def document_graph(self, document_id: uuid.UUID) -> DocumentGraph:
        summary = await self._graph.document_graph(str(document_id))
        if summary is None:
            raise NotFoundError(
                "Document not found in the knowledge graph (has it been synced?)"
            )
        return DocumentGraph(**summary)
