"""Schemas for the chat (RAG query) endpoint."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.query_intelligence import StructuredQueryRead


class ChatQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    include_external: bool | None = Field(
        default=None,
        description="Include external research paper sources (e.g. arXiv) in RAG retrieval",
    )


class CitationItem(BaseModel):
    marker: int
    document_id: uuid.UUID
    document_name: str
    version: int
    page: int | None
    chunk_id: uuid.UUID
    section: str | None
    score: float
    snippet: str
    retrievers: list[str]


class RetrievalInfo(BaseModel):
    route: str
    reasons: list[str]
    retriever_hits: dict[str, int]
    fallback_used: bool
    # Set when the query has temporal intent pointing at the past ("what
    # was the policy in 2023?") — chunks are drawn from each document's
    # version active as of this cutoff instead of its current version.
    as_of: datetime | None = None


class ConflictNoteItem(BaseModel):
    """Phase 13: a cross-document contradiction found among today's
    retrieval candidates. ``resolved`` true means the non-preferred claim
    was dropped from the LLM's context (``dropped_chunk_id``); false means
    authority couldn't decide, so both claims were kept and this is
    surfaced instead — "expose the conflict to the user."""

    claim_a_chunk_id: uuid.UUID
    claim_b_chunk_id: uuid.UUID
    contradiction_score: float
    preferred_chunk_id: uuid.UUID | None
    resolved: bool
    reason: str
    dropped_chunk_id: uuid.UUID | None


class ContextFusionInfo(BaseModel):
    """Transparency into Module 7: how the final context was assembled."""

    candidates: int
    after_dedup: int
    final_count: int
    reranker_model: str
    conflicts: list[ConflictNoteItem]


class CitationGenerationInfo(BaseModel):
    """Transparency into Module 8's Citation Generator stage: which of the
    sources offered to the LLM its answer actually cites."""

    cited: int
    invalid_markers: list[int]  # [n] markers in the answer with no matching source
    used_fallback: bool  # True when the answer had no [n] markers at all


class ClaimVerificationItem(BaseModel):
    """Module 9 per-claim result: Claim Extraction -> Evidence Retrieval ->
    Fact Verification -> Support Score -> Citation Verification."""

    claim: str
    support_score: float
    supported: bool
    verdict: str  # "entailment" | "contradiction" | "neutral" | "no_evidence"
    source: str | None
    version: int | None
    page: int | None
    chunk_id: uuid.UUID | None
    cited_markers: list[int]
    citation_verified: bool | None


class VerificationInfo(BaseModel):
    """Transparency into Module 9: whether/how the answer was verified."""

    enabled: bool
    model: str
    threshold: float
    claims_checked: int


class HistoryCitation(BaseModel):
    marker: int
    chunk_id: uuid.UUID
    snippet: str | None


class HistoryAnswer(BaseModel):
    id: uuid.UUID
    answer_text: str
    model: str | None
    latency_ms: float | None
    grounded: bool | None
    confidence: float | None
    created_at: datetime
    citations: list[HistoryCitation]


class HistoryItem(BaseModel):
    """One past turn: the question plus whatever answer(s) it produced."""

    query_id: uuid.UUID
    query_text: str
    intent: str | None
    created_at: datetime
    answers: list[HistoryAnswer]


class ChatHistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


class ChatQueryResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    query_id: uuid.UUID
    answer_id: uuid.UUID
    model: str
    retrieved_chunks: int
    latency_ms: float
    analysis: StructuredQueryRead
    retrieval: RetrievalInfo
    context_fusion: ContextFusionInfo
    citation_generation: CitationGenerationInfo
    confidence: float | None
    hallucination_detected: bool | None
    claim_verifications: list[ClaimVerificationItem]
    verification: VerificationInfo
