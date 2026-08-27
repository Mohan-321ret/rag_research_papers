"""Chat (RAG query) endpoints. All logic lives in the service layer."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ChatServiceDep, CurrentUserDep, QueryIntelligenceServiceDep
from app.schemas.chat import ChatHistoryResponse, ChatQueryRequest, ChatQueryResponse
from app.schemas.query_intelligence import StructuredQueryRead

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    summary="Ask a question over the knowledge base (baseline RAG)",
)
async def chat_query(
    payload: ChatQueryRequest, service: ChatServiceDep, user: CurrentUserDep
) -> ChatQueryResponse:
    return await service.query(user=user, request=payload)


@router.get(
    "/history",
    response_model=ChatHistoryResponse,
    summary="The caller's own past questions and answers, newest first",
)
async def chat_history(
    service: ChatServiceDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChatHistoryResponse:
    return await service.history(user=user, limit=limit, offset=offset)


@router.post(
    "/analyze",
    response_model=StructuredQueryRead,
    summary="Analyze a query without answering it (query intelligence)",
)
async def analyze_query(
    payload: ChatQueryRequest,
    service: QueryIntelligenceServiceDep,
    _user: CurrentUserDep,
) -> StructuredQueryRead:
    structured = await service.analyze(payload.query)
    return StructuredQueryRead.from_structured(structured)
