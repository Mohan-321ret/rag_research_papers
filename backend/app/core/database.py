"""Async SQLAlchemy engine and session management for PostgreSQL."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the (lazily created, cached) async database engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        connect_args={"timeout": settings.database_connect_timeout_seconds},
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the (cached) session factory bound to the engine."""
    return async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a database session per request."""
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the engine's connection pool (application shutdown)."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
