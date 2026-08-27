"""Schemas for the explicit search endpoints (Phase 15).

``/chat/query`` answers a question with an LLM; these endpoints return the
retrieved evidence itself, for UIs that want to browse sources directly
(a search results page) rather than read a generated answer.
"""

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    version: int
    page: int | None
    section: str | None
    score: float
    snippet: str
    retrievers: list[str]


class SearchResponse(BaseModel):
    query: str
    route: str  # which strategy actually ran
    total: int
    results: list[SearchHit]
    reasons: list[str]
    retriever_hits: dict[str, int]
    fallback_used: bool
