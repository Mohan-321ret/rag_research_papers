"""Schemas for the knowledge evolution endpoint (Module 3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConflictItem(BaseModel):
    old_sentence: str
    new_sentence: str
    contradiction_score: float


class VersionComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_version_number: int | None
    to_version_number: int
    change_type: str  # "created" | "revised"
    text_similarity: float
    added_count: int
    removed_count: int
    replaced_count: int
    added_sentences: list[str]
    removed_sentences: list[str]
    drift_score: float
    drift_magnitude: str
    conflicts: list[ConflictItem]
    has_conflict: bool
    vectors_added: int
    graph_synced: bool
    summary: str
    created_at: datetime


class EvolutionHistoryResponse(BaseModel):
    document_id: uuid.UUID
    comparisons: list[VersionComparisonRead]


class ChangedChunkItem(BaseModel):
    old_chunk_id: uuid.UUID | None
    new_chunk_id: uuid.UUID | None
    old_content: str | None
    new_content: str | None
    drift_score: float
    # "rewording" | "expansion" | "narrowing" | "contradiction" |
    # "topic_shift" | "removed" | "added"
    drift_type: str


class ConceptDriftReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    old_version_number: int | None
    new_version_number: int
    drift_score: float
    drift_type: str
    changed_chunks: list[ChangedChunkItem]
    created_at: datetime  # the record's timestamp


class ConceptDriftHistoryResponse(BaseModel):
    document_id: uuid.UUID
    reports: list[ConceptDriftReportRead]
