"""Schemas for the analytics endpoints (Phase 15)."""

from pydantic import BaseModel


class CorpusStats(BaseModel):
    documents: int
    versions: int
    chunks: int
    entities: int
    documents_by_status: dict[str, int]


class UsageStats(BaseModel):
    queries: int
    answers: int
    feedback_by_rating: dict[str, int]


class QualityStats(BaseModel):
    """Averages over what Modules 8-9 recorded on each answer."""

    avg_latency_ms: float | None
    avg_confidence: float | None
    ungrounded_answers: int


class DashboardResponse(BaseModel):
    corpus: CorpusStats
    usage: UsageStats
    quality: QualityStats
    drift: dict[str, int]
    conflicts: int


class MetricsResponse(BaseModel):
    """Breakdowns behind the dashboard headline numbers."""

    intents: dict[str, int]
    retrievers: dict[str, int]
    entity_types: dict[str, int]
    drift_magnitudes: dict[str, int]
    documents_by_status: dict[str, int]
    feedback_by_rating: dict[str, int]
