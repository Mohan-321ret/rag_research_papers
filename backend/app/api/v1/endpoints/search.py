"""Explicit search endpoints. All logic lives in SearchService."""

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SearchServiceDep
from app.modules.retrieval.router import RetrievalRoute
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "/semantic",
    response_model=SearchResponse,
    summary="Dense vector search (embeddings only), returning ranked evidence",
)
async def semantic_search(
    request: SearchRequest, service: SearchServiceDep, _user: CurrentUserDep
) -> SearchResponse:
    return await service.search(request, route=RetrievalRoute.VECTOR)


@router.post(
    "/hybrid",
    response_model=SearchResponse,
    summary="Hybrid search: BM25 + vector + graph, fused by Reciprocal Rank Fusion",
)
async def hybrid_search(
    request: SearchRequest, service: SearchServiceDep, _user: CurrentUserDep
) -> SearchResponse:
    return await service.search(request, route=RetrievalRoute.HYBRID)
