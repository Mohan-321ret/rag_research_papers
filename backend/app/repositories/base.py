"""Common repository base class."""

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base class for repositories; owns the request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session
