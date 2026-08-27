"""Knowledge graph endpoints. All logic lives in GraphService."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, GraphServiceDep
from app.schemas.graph import DocumentGraph, GraphStats, GraphSyncResult

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats", response_model=GraphStats, summary="Node/relationship counts")
async def graph_stats(service: GraphServiceDep, _user: CurrentUserDep) -> GraphStats:
    return await service.stats()


@router.post(
    "/documents/{document_id}/sync",
    response_model=GraphSyncResult,
    summary="Sync (or re-sync) a document into the knowledge graph",
)
async def sync_document_graph(
    document_id: uuid.UUID, service: GraphServiceDep, _user: CurrentUserDep
) -> GraphSyncResult:
    return await service.sync_document(document_id)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentGraph,
    summary="Graph neighborhood of a document",
)
async def get_document_graph(
    document_id: uuid.UUID, service: GraphServiceDep, _user: CurrentUserDep
) -> DocumentGraph:
    return await service.document_graph(document_id)
