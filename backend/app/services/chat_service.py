"""Baseline RAG chat service.

Question -> query intelligence -> adaptive retrieval router (BM25 /
vector / graph / hybrid, over-fetching a candidate pool) -> context
fusion (dedup -> cross-encoder rerank -> compression to the final top-K
-> SOURCE-N context blocks) -> enterprise LLM generation (Prompt
Constructor -> LLMProvider -> Citation Generator) -> answer + citations.

Every step is persisted, and the evidence tables now mean three
different things: ``retrieval_logs`` is the full raw candidate pool the
router returned (rank/score/retriever, for evaluating routing and fusion
later); the SOURCE blocks context-fusion builds are everything *offered*
to the LLM; and ``citations`` is only the subset the Citation Generator
found the answer actually references (falling back to all offered
sources if the model produced no [n] markers at all).
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.user import User
from app.modules.llm.generator import build_answer_generator
from app.repositories.interaction_repository import InteractionRepository
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatQueryRequest,
    ChatQueryResponse,
    CitationGenerationInfo,
    CitationItem,
    ClaimVerificationItem,
    ConflictNoteItem,
    ContextFusionInfo,
    HistoryAnswer,
    HistoryCitation,
    HistoryItem,
    RetrievalInfo,
    VerificationInfo,
)
from app.schemas.query_intelligence import StructuredQueryRead
from app.services.context_fusion_service import ContextFusionService
from app.services.query_intelligence_service import QueryIntelligenceService
from app.services.retrieval_service import RetrievalService
from app.services.verification_service import VerificationService

from app.repositories.chunk_repository import ChunkRepository

logger = get_logger(__name__)

_SNIPPET_CHARS = 240


class ChatService:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        interaction_repository: InteractionRepository,
        query_intelligence: QueryIntelligenceService,
        retrieval: RetrievalService,
        context_fusion: ContextFusionService,
        verification: VerificationService,
    ) -> None:
        self._settings = settings
        self._session = session
        self._interactions = interaction_repository
        self._chunks = ChunkRepository(session)
        self._query_intelligence = query_intelligence
        self._retrieval = retrieval
        self._context_fusion = context_fusion
        self._verification = verification
        self._generator = build_answer_generator(settings)

    async def history(
        self, *, user: User, limit: int, offset: int
    ) -> ChatHistoryResponse:
        """The caller's own past turns, newest first. Scoped to the
        authenticated user — one user's questions are never visible to
        another through this endpoint."""
        queries, total = await self._interactions.list_history(
            user_id=user.id, limit=limit, offset=offset
        )
        return ChatHistoryResponse(
            items=[
                HistoryItem(
                    query_id=query.id,
                    query_text=query.query_text,
                    intent=query.intent,
                    created_at=query.created_at,
                    answers=[
                        HistoryAnswer(
                            id=answer.id,
                            answer_text=answer.answer_text,
                            model=answer.model,
                            latency_ms=answer.latency_ms,
                            grounded=answer.grounded,
                            confidence=answer.confidence,
                            created_at=answer.created_at,
                            citations=[
                                HistoryCitation(
                                    marker=citation.marker,
                                    chunk_id=citation.chunk_id,
                                    snippet=citation.snippet,
                                )
                                for citation in sorted(
                                    answer.citations, key=lambda c: c.marker
                                )
                            ],
                        )
                        for answer in query.answers
                    ],
                )
                for query in queries
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def query(self, *, user: User, request: ChatQueryRequest) -> ChatQueryResponse:
        started = time.perf_counter()
        final_k = request.top_k or self._settings.context_top_k
        candidate_k = max(final_k, self._settings.retrieval_candidate_k)

        analysis = await self._query_intelligence.analyze(request.query)
        query_row = await self._interactions.create_query(
            user_id=user.id,
            query_text=request.query,
            normalized_text=analysis.normalized_query,
            intent=analysis.intent.value,
        )

        # Module 6: route to BM25/vector/graph/hybrid, over-fetching a
        # candidate pool for the fusion pipeline to work with.
        retrieval = await self._retrieval.retrieve(
            request.query, analysis, candidate_k, include_external=request.include_external
        )

        # Module 7: dedup -> rerank -> compress -> SOURCE-N context blocks.
        fusion = await self._context_fusion.fuse(request.query, retrieval.items, final_k)

        # Module 8: Prompt Constructor -> LLMProvider -> Citation Generator.
        generation = await self._generator.generate(request.query, fusion.blocks)

        # Module 9: Claim Extraction -> Evidence Retrieval -> Fact
        # Verification -> Confidence Scoring -> Hallucination Detection ->
        # Response Refinement. Runs against the offered SOURCE blocks
        # (fusion.items) plus an independent corpus-wide search per claim.
        verification = await self._verification.verify(generation.text, fusion.items)
        final_answer_text = verification.refined_answer
        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        # The full raw candidate pool, for evaluating routing/fusion later.
        # Filter to chunks present in the DB to satisfy FK constraints for external arXiv hits.
        candidate_chunk_ids = [hit.item.chunk.id for hit in retrieval.items]
        valid_log_ids = await self._chunks.filter_existing_chunk_ids(candidate_chunk_ids)

        await self._interactions.add_retrieval_logs(
            query_row.id,
            [
                (hit.item.chunk.id, rank, hit.score, "+".join(hit.retrievers))
                for rank, hit in enumerate(retrieval.items, start=1)
                if hit.item.chunk.id in valid_log_ids
            ],
        )
        answer_row = await self._interactions.create_answer(
            query_id=query_row.id,
            answer_text=final_answer_text,
            model=generation.model,
            prompt_tokens=generation.input_tokens,
            completion_tokens=generation.output_tokens,
            latency_ms=latency_ms,
            grounded=(not verification.hallucination_detected) if verification.enabled else None,
            confidence=verification.confidence,
        )

        # Only the sources the Citation Generator found the answer actually
        # references (fusion.blocks/fusion.items share the same 1-based
        # numbering, so a cited marker indexes directly into fusion.items).
        cited_items = [
            (marker, fusion.items[marker - 1])
            for marker in generation.cited_markers
            if 1 <= marker <= len(fusion.items)
        ]
        cited_chunk_ids = [item.chunk_id for _, item in cited_items]
        valid_citation_ids = await self._chunks.filter_existing_chunk_ids(cited_chunk_ids)

        await self._interactions.add_citations(
            answer_row.id,
            [
                (item.chunk_id, marker, item.content[:_SNIPPET_CHARS])
                for marker, item in cited_items
                if item.chunk_id in valid_citation_ids
            ],
        )
        await self._session.commit()

        logger.info(
            "chat_query_answered",
            query_id=str(query_row.id),
            route=retrieval.route.value,
            candidates=fusion.candidates_in,
            offered=fusion.final_count,
            cited=len(cited_items),
            model=generation.model,
            confidence=verification.confidence,
            hallucination_detected=verification.hallucination_detected,
            latency_ms=latency_ms,
        )
        return ChatQueryResponse(
            answer=final_answer_text,
            citations=[
                CitationItem(
                    marker=marker,
                    document_id=item.document_id,
                    document_name=item.document_title,
                    version=item.version_number,
                    page=item.page_number,
                    chunk_id=item.chunk_id,
                    section=item.section,
                    score=round(item.rerank_score or 0.0, 4),
                    snippet=item.content[:_SNIPPET_CHARS],
                    retrievers=item.retrievers,
                )
                for marker, item in cited_items
            ],
            query_id=query_row.id,
            answer_id=answer_row.id,
            model=generation.model,
            retrieved_chunks=len(cited_items),
            latency_ms=latency_ms,
            analysis=StructuredQueryRead.from_structured(analysis),
            retrieval=RetrievalInfo(
                route=retrieval.route.value,
                reasons=retrieval.reasons,
                retriever_hits=retrieval.retriever_hits,
                fallback_used=retrieval.fallback_used,
                as_of=retrieval.as_of,
            ),
            context_fusion=ContextFusionInfo(
                candidates=fusion.candidates_in,
                after_dedup=fusion.after_dedup,
                final_count=fusion.final_count,
                reranker_model=fusion.reranker_model,
                conflicts=[
                    ConflictNoteItem(
                        claim_a_chunk_id=note.claim_a_chunk_id,
                        claim_b_chunk_id=note.claim_b_chunk_id,
                        contradiction_score=note.contradiction_score,
                        preferred_chunk_id=note.preferred_chunk_id,
                        resolved=note.resolved,
                        reason=note.reason,
                        dropped_chunk_id=note.dropped_chunk_id,
                    )
                    for note in fusion.conflicts
                ],
            ),
            citation_generation=CitationGenerationInfo(
                cited=len(cited_items),
                invalid_markers=generation.invalid_markers,
                used_fallback=generation.used_fallback,
            ),
            confidence=verification.confidence,
            hallucination_detected=verification.hallucination_detected,
            claim_verifications=[
                ClaimVerificationItem(
                    claim=cv.claim,
                    support_score=cv.support_score,
                    supported=cv.supported,
                    verdict=cv.verdict,
                    source=cv.source_document,
                    version=cv.source_version,
                    page=cv.source_page,
                    chunk_id=cv.source_chunk_id,
                    cited_markers=cv.cited_markers,
                    citation_verified=cv.citation_verified,
                )
                for cv in verification.claim_verifications
            ],
            verification=VerificationInfo(
                enabled=verification.enabled,
                model=verification.model_name,
                threshold=self._settings.verification_support_threshold,
                claims_checked=len(verification.claim_verifications),
            ),
        )
