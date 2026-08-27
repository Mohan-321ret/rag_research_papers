"""Repository for system-level database operations (connectivity checks)."""

from sqlalchemy import text

from app.repositories.base import BaseRepository


class SystemRepository(BaseRepository):
    """Low-level system queries against PostgreSQL."""

    async def ping(self) -> None:
        """Execute a trivial query; raises if the database is unreachable."""
        await self._session.execute(text("SELECT 1"))
