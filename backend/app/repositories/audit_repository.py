"""Data access for the audit trail."""

import uuid
from typing import Any

from sqlalchemy import func, select

from app.models.system import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    async def record(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_logs(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[list[AuditLog], int]:
        query = select(AuditLog)
        if action:
            query = query.where(AuditLog.action == action)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)

        total = await self._session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        result = await self._session.execute(
            query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)
