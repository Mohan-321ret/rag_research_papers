"""Aggregated router for all /api/v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    analytics,
    auth,
    chat,
    conflicts,
    documents,
    feedback,
    graph,
    health,
    knowledge,
    search,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(graph.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(conflicts.router)
api_v1_router.include_router(search.router)
api_v1_router.include_router(knowledge.router)
api_v1_router.include_router(feedback.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(admin.router)
