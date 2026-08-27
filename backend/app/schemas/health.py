"""Schemas for the health endpoint."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ComponentState = Literal["up", "down"]


class ComponentStatus(BaseModel):
    """Status of a single infrastructure dependency."""

    model_config = ConfigDict(frozen=True)

    status: ComponentState
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    """Overall service health, including per-component statuses."""

    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    timestamp: datetime
    components: dict[str, ComponentStatus]
