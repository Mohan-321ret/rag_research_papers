"""Explicit search service (Phase 15).

``/chat/query`` runs the full RAG pipeline and returns a generated answer.
These endpoints stop after retrieval + fusion and return the evidence
itself — what a search results page needs. They reuse Modules 6 and 7
rather than reimplementing retrieval, and simply pin the route the
adaptive router would otherwise have chosen:

    /search/semantic -> vector (dense embeddings only)
    /search/hybrid   -> BM25 + vector + graph, fused by RRF
"""

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.retrieval.router import RetrievalRoute
from app.schemas.search import SearchHit, SearchRequest, SearchResponse
from app.services.context_fusion_service import ContextFusionService
from app.services.query_intelligence_service import QueryIntelligenceService
from app.services.retrieval_service import RetrievalService

logger = get_logger(__name__)

_SNIPPET_CHARS = 400


class SearchService:
    def __init__(
        self,
        settings: Settings,
        query_intelligence: QueryIntelligenceService,
        retrieval: RetrievalService,
        context_fusion: ContextFusionService,
    ) -> None:
        self._settings = settings
        self._query_intelligence = query_intelligence
        self._retrieval = retrieval
        self._context_fusion = context_fusion

    async def search(
        self, request: SearchRequest, *, route: RetrievalRoute
    ) -> SearchResponse:
        final_k = request.top_k or self._settings.context_top_k
        candidate_k = max(final_k, self._settings.retrieval_candidate_k)

        analysis = await self._query_intelligence.analyze(request.query)
        retrieval = await self._retrieval.retrieve(
            request.query, analysis, candidate_k, force_route=route
        )
        # Reuse Module 7 so search results get the same dedup + reranking
        # (and Phase 13 conflict resolution) the LLM path gets.
        fusion = await self._context_fusion.fuse(request.query, retrieval.items, final_k)

        logger.info(
            "search_executed",
            route=route.value,
            candidates=fusion.candidates_in,
            returned=fusion.final_count,
        )
        return SearchResponse(
            query=request.query,
            route=retrieval.route.value,
            total=len(fusion.items),
            results=[
                SearchHit(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    document_name=item.document_title,
                    version=item.version_number,
                    page=item.page_number,
                    section=item.section,
                    score=round(item.rerank_score or item.retrieval_score, 4),
                    snippet=item.content[:_SNIPPET_CHARS],
                    retrievers=item.retrievers,
                )
                for item in fusion.items
            ],
            reasons=retrieval.reasons,
            retriever_hits=retrieval.retriever_hits,
            fallback_used=retrieval.fallback_used,
        )
