"""Admin endpoints. All logic lives in AdminService.

Guarded by the ADMIN role: these expose operational internals and every
user's audit trail, so they are deliberately not open to ordinary
accounts (registration creates USER). Promote an account with:

    UPDATE users SET role = 'ADMIN' WHERE email = '...';
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminServiceDep, require_roles
from app.models.user import UserRole
from app.schemas.admin import AuditLogListResponse, SystemStatusResponse

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[require_roles(UserRole.ADMIN)],
)


@router.get(
    "/system-status",
    response_model=SystemStatusResponse,
    summary="Infrastructure health, which ML modules are live, and corpus size",
)
async def system_status(service: AdminServiceDep) -> SystemStatusResponse:
    return await service.system_status()


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Audit trail, newest first",
)
async def audit_logs(
    service: AdminServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=100)] = None,
    user_id: uuid.UUID | None = None,
) -> AuditLogListResponse:
    return await service.audit_logs(
        limit=limit, offset=offset, action=action, user_id=user_id
    )
