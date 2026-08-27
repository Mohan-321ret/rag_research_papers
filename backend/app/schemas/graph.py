"""Schemas for knowledge graph endpoints."""

import uuid
from typing import Any

from pydantic import BaseModel


class GraphSyncResult(BaseModel):
    document_id: uuid.UUID
    versions: int
    chunks: int
    entities: int
    topics: int


class GraphStats(BaseModel):
    nodes: dict[str, int]
    relationships: dict[str, int]


class GraphVersionNode(BaseModel):
    id: str
    number: int
    is_current: bool


class DocumentGraph(BaseModel):
    document_id: uuid.UUID
    title: str
    versions: list[GraphVersionNode]
    chunk_count: int
    entities: list[dict[str, Any]]
    authors: list[str]
    departments: list[str]
    topics: list[str]
