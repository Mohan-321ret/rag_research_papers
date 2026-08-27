"""Health-check service: probes infrastructure dependencies."""

import asyncio
import time
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.neo4j import Neo4jClient
from app.repositories.system_repository import SystemRepository
from app.schemas.health import ComponentStatus, HealthResponse

logger = get_logger(__name__)

_PROBE_TIMEOUT_SECONDS = 5.0


class HealthService:
    """Aggregates the health of the API and its backing services."""

    def __init__(
        self,
        settings: Settings,
        system_repository: SystemRepository,
        neo4j_client: Neo4jClient,
    ) -> None:
        self._settings = settings
        self._system_repository = system_repository
        self._neo4j_client = neo4j_client

    async def get_health(self) -> HealthResponse:
        database, graph = await asyncio.gather(
            self._probe("postgres", self._system_repository.ping()),
            self._probe("neo4j", self._neo4j_client.verify_connectivity()),
        )
        components = {"database": database, "graph_database": graph}
        overall = "ok" if all(c.status == "up" for c in components.values()) else "degraded"
        return HealthResponse(
            status=overall,
            app=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.environment,
            timestamp=datetime.now(UTC),
            components=components,
        )

    @staticmethod
    async def _probe(name: str, check: Coroutine[Any, Any, None]) -> ComponentStatus:
        """Run a connectivity check, converting failures into a 'down' status."""
        start = time.perf_counter()
        try:
            await asyncio.wait_for(check, timeout=_PROBE_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning("health_probe_failed", component=name, error=str(exc))
            return ComponentStatus(status="down", detail=type(exc).__name__)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return ComponentStatus(status="up", latency_ms=latency_ms)
