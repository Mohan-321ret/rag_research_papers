"""Tests for the analytics and admin endpoints (Phase 15):
/analytics/dashboard, /analytics/metrics, /admin/system-status,
/admin/audit-logs — plus the ADMIN role guard.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.user import User, UserRole

DOC = b"1. Leave Policy\nEmployees at Acme receive 25 days of paid annual leave.\n"


def _upload(client: TestClient, headers, filename: str = "an.txt", content: bytes = DOC):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _promote_to_admin(test_db_engine, email_token_headers, client: TestClient) -> None:
    """Registration creates USER; /admin needs ADMIN. Promote the caller
    directly in the DB, the same way an operator would."""
    me = client.get("/api/v1/auth/me", headers=email_token_headers).json()

    async def promote() -> None:
        factory = async_sessionmaker(test_db_engine, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                update(User).where(User.id == uuid.UUID(me["id"])).values(role=UserRole.ADMIN)
            )
            await session.commit()

    asyncio.run(promote())


# ---- analytics ----------------------------------------------------------


def test_dashboard_shape(client: TestClient, auth_headers) -> None:
    body = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()

    assert set(body) == {"corpus", "usage", "quality", "drift", "conflicts"}
    assert set(body["corpus"]) == {
        "documents", "versions", "chunks", "entities", "documents_by_status",
    }
    assert set(body["usage"]) == {"queries", "answers", "feedback_by_rating"}
    assert set(body["quality"]) == {
        "avg_latency_ms", "avg_confidence", "ungrounded_answers",
    }
    assert isinstance(body["conflicts"], int)


def test_dashboard_counts_move_with_uploads(client: TestClient, auth_headers) -> None:
    before = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    _upload(client, auth_headers, "counted.txt")
    after = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()

    assert after["corpus"]["documents"] == before["corpus"]["documents"] + 1
    assert after["corpus"]["versions"] == before["corpus"]["versions"] + 1
    assert after["corpus"]["chunks"] > before["corpus"]["chunks"]


def test_dashboard_usage_moves_with_queries(client: TestClient, auth_headers) -> None:
    before = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    client.post("/api/v1/chat/query", headers=auth_headers, json={"query": "anything"})
    after = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()

    assert after["usage"]["queries"] == before["usage"]["queries"] + 1
    assert after["usage"]["answers"] == before["usage"]["answers"] + 1


def test_metrics_shape(client: TestClient, auth_headers) -> None:
    _upload(client, auth_headers, "metrics.txt")
    client.post("/api/v1/chat/query", headers=auth_headers, json={"query": "leave days"})

    body = client.get("/api/v1/analytics/metrics", headers=auth_headers).json()
    assert set(body) == {
        "intents", "retrievers", "entity_types", "drift_magnitudes",
        "documents_by_status", "feedback_by_rating",
    }
    assert all(isinstance(v, dict) for v in body.values())
    # A query was just run, so its intent is counted.
    assert sum(body["intents"].values()) >= 1


def test_analytics_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/analytics/dashboard").status_code == 401
    assert client.get("/api/v1/analytics/metrics").status_code == 401


# ---- admin --------------------------------------------------------------


def test_admin_forbidden_for_normal_user(client: TestClient, auth_headers) -> None:
    """Registration creates a USER; admin endpoints expose operational
    internals and everyone's audit trail, so they must be refused."""
    assert client.get("/api/v1/admin/system-status", headers=auth_headers).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=auth_headers).status_code == 403


def test_admin_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/admin/system-status").status_code == 401
    assert client.get("/api/v1/admin/audit-logs").status_code == 401


def test_system_status_for_admin(client: TestClient, auth_headers, test_db_engine) -> None:
    _promote_to_admin(test_db_engine, auth_headers, client)

    response = client.get("/api/v1/admin/system-status", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert set(body) == {
        "status", "app", "version", "environment", "timestamp",
        "components", "modules", "corpus",
    }
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body["components"]

    modules = {m["name"]: m for m in body["modules"]}
    assert {
        "embeddings", "reranker", "verification", "knowledge_evolution",
        "conflict_detection", "incremental_reindex", "llm", "graph_sync",
    } <= set(modules)
    # conftest disables these for test speed — status must reflect reality,
    # not just what config claims in isolation.
    assert modules["verification"]["enabled"] is False
    assert modules["conflict_detection"]["enabled"] is False
    assert modules["incremental_reindex"]["enabled"] is True
    assert set(body["corpus"]) == {"documents", "versions", "chunks", "entities"}


def test_audit_logs_for_admin(client: TestClient, auth_headers, test_db_engine) -> None:
    _upload(client, auth_headers, "audited.txt")
    _promote_to_admin(test_db_engine, auth_headers, client)

    response = client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["total"] >= 1
    entry = body["items"][0]
    assert set(entry) == {
        "id", "user_id", "action", "resource_type", "resource_id",
        "details", "created_at",
    }
    assert any(item["action"] == "document.upload" for item in body["items"])


def test_audit_logs_filter_by_action(client: TestClient, auth_headers, test_db_engine) -> None:
    _upload(client, auth_headers, "filtered_audit.txt")
    _promote_to_admin(test_db_engine, auth_headers, client)

    body = client.get(
        "/api/v1/admin/audit-logs?action=document.upload", headers=auth_headers
    ).json()
    assert body["total"] >= 1
    assert all(item["action"] == "document.upload" for item in body["items"])
