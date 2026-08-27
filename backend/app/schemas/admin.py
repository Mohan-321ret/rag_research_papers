"""Schemas for the admin endpoints (Phase 15)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.health import ComponentStatus


class ModuleStatus(BaseModel):
    """Whether each optional ML/analysis feature is actually live right now
    — enabled in config *and* with its dependency importable."""

    name: str
    enabled: bool
    detail: str | None = None


class SystemStatusResponse(BaseModel):
    status: str  # "ok" | "degraded"
    app: str
    version: str
    environment: str
    timestamp: datetime
    components: dict[str, ComponentStatus]
    modules: list[ModuleStatus]
    corpus: dict[str, int]


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int
