"""Data access for user accounts."""

import uuid

from sqlalchemy import select

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None,
        role: UserRole = UserRole.USER,
    ) -> User:
        user = User(
            email=email, hashed_password=hashed_password, full_name=full_name, role=role
        )
        self._session.add(user)
        await self._session.flush()
        return user
