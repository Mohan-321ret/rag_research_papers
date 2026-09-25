"""Adaptive retrieval service (Module 6).

Query intelligence output -> retrieval router -> BM25 / vector / graph
(-> hybrid fusion via RRF) -> ranked, hydrated current-version chunks.

Robustness rules:
- Graph retrieval degrades to an empty list when Neo4j is down.
- A non-vector route that returns nothing falls back to vector search,
  so exotic routing can never make answers strictly worse.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.processing.embedding import SentenceTransformerEmbedder
from app.modules.query_intelligence.analyzer import StructuredQuery
from app.modules.repository.graph_store import GraphStore
from app.modules.repository.vector_store import get_vector_store
from app.modules.retrieval.bm25_index import get_bm25_index
from app.modules.retrieval.fusion import reciprocal_rank_fusion
from app.modules.retrieval.router import RetrievalRoute, decide_route
from app.modules.retrieval.temporal import resolve_as_of_cutoff
from app.repositories.chunk_repository import ChunkRepository, RetrievableChunk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievedItem:
    item: RetrievableChunk
    score: float
    retrievers: list[str]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    route: RetrievalRoute
    reasons: list[str]
    retriever_hits: dict[str, int]
    fallback_used: bool
    items: list[RetrievedItem] = field(default_factory=list)
    as_of: datetime | None = None


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        chunk_repository: ChunkRepository,
        embedder: SentenceTransformerEmbedder,
        graph_store: GraphStore,
    ) -> None:
        self._settings = settings
        self._chunks = chunk_repository
        self._embedder = embedder
        self._graph = graph_store

    async def retrieve(
        self,
        query_text: str,
        structured: StructuredQuery,
        top_k: int,
        *,
        force_route: RetrievalRoute | None = None,
        include_external: bool | None = None,
    ) -> RetrievalResult:
        """``force_route`` bypasses the adaptive router — used by the explicit
        /search/semantic and /search/hybrid endpoints, where the caller has
        already chosen the strategy. /chat/query leaves it unset so Module 6
        keeps deciding."""
        decision = decide_route(structured)
        route = force_route or decision.route
        reasons = (
            [f"explicitly requested {force_route.value} search"]
            if force_route is not None
            else decision.reasons
        )
        # Temporal intent pointing at the past ("before 2024", "as of
        # 2023") resolves to a cutoff: retrieve each document's version
        # active at that time instead of its current one. Vector search is
        # the router's default for exactly this kind of conceptual/
        # historical question; BM25/graph only ever index current content,
        # so under an as-of cutoff they contribute nothing (see
        # ChunkRepository.get_as_of_by_ids).
        as_of = resolve_as_of_cutoff(structured.temporal_direction, structured.target_date)

        # chunk_id (str) -> ordered best-first, per retriever.
        ranked_lists: dict[str, list[str]] = {}
        native_scores: dict[str, dict[str, float]] = {}

        async def run(name: str) -> None:
            if name == "vector":
                hits = await self._vector_hits(query_text, structured, top_k, as_of)
            elif name == "bm25":
                hits = await self._bm25_hits(query_text, top_k)
            else:
                hits = await self._graph_hits(structured, top_k)
            ranked_lists[name] = [key for key, _ in hits]
            native_scores[name] = dict(hits)

        if route == RetrievalRoute.HYBRID:
            for name in ("vector", "bm25", "graph"):
                await run(name)
        else:
            await run(route.value)

        fallback_used = False
        if route != RetrievalRoute.VECTOR and not any(ranked_lists.values()):
            # Primary retriever came up empty — fall back to dense search.
            await run("vector")
            fallback_used = True

        items = await self._rank_and_hydrate(ranked_lists, native_scores, top_k, as_of)
        
        should_fetch_external = (include_external is True)
        if should_fetch_external:
            ext_items = await self._external_arxiv_hits(query_text, top_k)
            if ext_items:
                items.extend(ext_items)
                ranked_lists["arxiv"] = [str(it.item.chunk.id) for it in ext_items]

        result = RetrievalResult(
            route=route,
            reasons=reasons,
            retriever_hits={name: len(ids) for name, ids in ranked_lists.items()},
            fallback_used=fallback_used,
            items=items,
            as_of=as_of,
        )
        logger.info(
            "retrieval_routed",
            route=route.value,
            reasons=reasons,
            hits=result.retriever_hits,
            fallback=fallback_used,
            returned=len(items),
            as_of=as_of.isoformat() if as_of else None,
        )
        return result

    # ---- retrievers -------------------------------------------------------

    async def _vector_hits(
        self,
        query_text: str,
        structured: StructuredQuery,
        top_k: int,
        as_of: datetime | None,
    ) -> list[tuple[str, float]]:
        """Dense retrieval; returns (chunk_id, cosine score) best-first."""
        search_texts = [query_text]
        if structured.expanded_query:
            search_texts.append(" ".join(structured.expanded_query[:4]))
        vectors = await self._embedder.embed_texts(search_texts)
        store = await get_vector_store(
            self._settings.vector_index_dir,
            self._embedder.dimension,
            self._embedder.model_name,
        )
        best: dict[str, float] = {}
        for vector in vectors:
            for hit in await store.search(vector, k=top_k * 3):
                if hit.score >= self._settings.retrieval_min_score:
                    best[hit.chunk_id] = max(best.get(hit.chunk_id, -1.0), hit.score)
        # Resolve embedding refs -> chunk ids, scoped to the current or
        # as-of version per document.
        by_ref = (
            await self._chunks.get_as_of_by_embedding_refs(list(best), as_of)
            if as_of is not None
            else await self._chunks.get_current_by_embedding_refs(list(best))
        )
        resolved = [
            (str(retrievable.chunk.id), score)
            for ref, score in best.items()
            if (retrievable := by_ref.get(ref)) is not None
        ]
        return sorted(resolved, key=lambda kv: kv[1], reverse=True)

    async def _bm25_hits(self, query_text: str, top_k: int) -> list[tuple[str, float]]:
        index = get_bm25_index()
        fingerprint = await self._chunks.corpus_fingerprint()
        await index.ensure_built(fingerprint, self._chunks.list_current_corpus)
        hits = await index.search(query_text, k=top_k * 2)
        return [(str(hit.chunk_id), hit.score) for hit in hits]

    async def _graph_hits(
        self, structured: StructuredQuery, top_k: int
    ) -> list[tuple[str, float]]:
        terms = structured.entities or structured.keywords[:4]
        try:
            hits = await self._graph.chunks_mentioning(terms, limit=top_k * 2)
        except Exception as exc:
            logger.warning("graph_retrieval_unavailable", error=type(exc).__name__)
            return []
        return [(chunk_id, score) for chunk_id, score in hits]

    # ---- ranking ----------------------------------------------------------

    async def _rank_and_hydrate(
        self,
        ranked_lists: dict[str, list[str]],
        native_scores: dict[str, dict[str, float]],
        top_k: int,
        as_of: datetime | None,
    ) -> list[RetrievedItem]:
        populated = {name: ids for name, ids in ranked_lists.items() if ids}
        if not populated:
            return []

        if len(populated) == 1:
            # Single retriever: keep its native ordering and scores.
            [(name, ids)] = populated.items()
            ordered = [(key, native_scores[name][key], [name]) for key in ids]
        else:
            fused = reciprocal_rank_fusion(populated)
            ordered = [(hit.key, hit.score, hit.retrievers) for hit in fused]

        ids = [uuid.UUID(key) for key, _, _ in ordered]
        by_id = (
            await self._chunks.get_as_of_by_ids(ids, as_of)
            if as_of is not None
            else await self._chunks.get_current_by_ids(ids)
        )
        items: list[RetrievedItem] = []
        for key, score, retrievers in ordered:
            retrievable = by_id.get(uuid.UUID(key))
            if retrievable is not None:
                items.append(
                    RetrievedItem(
                        item=retrievable, score=round(score, 4), retrievers=retrievers
                    )
                )
            if len(items) >= top_k:
                break
        return items

    async def _external_arxiv_hits(
        self, query_text: str, top_k: int
    ) -> list[RetrievedItem]:
        from app.models.document import DocumentChunk
        from app.repositories.chunk_repository import RetrievableChunk
        from app.services.external_sources_service import search_arxiv

        try:
            papers = await search_arxiv(query_text, max_results=min(top_k, 5))
        except Exception as exc:
            logger.warning("external_arxiv_retrieval_failed", error=str(exc))
            return []

        items: list[RetrievedItem] = []
        for p in papers:
            chunk_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"arxiv:{p.external_id}")
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"doc:arxiv:{p.external_id}")
            content = (
                f"Title: {p.title}\n"
                f"Authors: {p.authors or 'Unknown'}\n"
                f"Published: {p.published or 'N/A'}\n"
                f"Source: arXiv ({p.external_id})\n"
                f"URL: {p.url}\n\n"
                f"Abstract:\n{p.abstract}"
            )
            mock_chunk = DocumentChunk(
                id=chunk_uuid,
                version_id=doc_uuid,
                document_id=doc_uuid,
                chunk_index=0,
                content=content,
                section="arXiv Abstract",
                page_number=1,
                token_count=len(content.split()),
                embedding_ref=f"arxiv_{p.external_id}",
            )
            retrievable = RetrievableChunk(
                chunk=mock_chunk,
                document_title=f"[arXiv] {p.title}",
                version_number=1,
            )
            items.append(
                RetrievedItem(
                    item=retrievable,
                    score=0.75,
                    retrievers=["arxiv"],
                )
            )
        return items
