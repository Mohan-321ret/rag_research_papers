"""Knowledge conflict endpoints (Phase 13). All logic lives in ConflictService."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ConflictServiceDep, CurrentUserDep
from app.schemas.conflict import ConflictListResponse, KnowledgeConflictRead

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get(
    "",
    response_model=ConflictListResponse,
    summary="Cross-document contradictions detected corpus-wide, with authority resolution",
)
async def list_conflicts(
    service: ConflictServiceDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConflictListResponse:
    items, total = await service.list_all(limit=limit, offset=offset)
    return ConflictListResponse(
        items=[KnowledgeConflictRead.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )
