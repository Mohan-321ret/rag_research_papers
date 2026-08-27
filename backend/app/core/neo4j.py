"""Async Neo4j driver lifecycle management."""

from functools import lru_cache

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import get_settings


class Neo4jClient:
    """Thin wrapper owning the async Neo4j driver.

    The driver is created lazily so importing the application does not
    require a reachable Neo4j instance.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._auth = (user, password)
        self._driver: AsyncDriver | None = None

    @property
    def driver(self) -> AsyncDriver:
        if self._driver is None:
            # Short connection timeout so a down Neo4j degrades requests
            # quickly instead of stalling them for the default ~30s.
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=self._auth,
                connection_timeout=5.0,
                max_connection_pool_size=20,
            )
        return self._driver

    async def verify_connectivity(self) -> None:
        """Raise if the Neo4j server is unreachable."""
        await self.driver.verify_connectivity()

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None


@lru_cache
def get_neo4j_client() -> Neo4jClient:
    """Return the (cached) application-wide Neo4j client."""
    settings = get_settings()
    return Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
