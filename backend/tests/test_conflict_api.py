"""API-level tests for cross-document knowledge conflicts (Phase 13):
GET /api/v1/conflicts, GET /api/v1/documents/{id}/conflicts, and the
priority upload parameter.

Conflict *detection* needs real embeddings to find that two differently
worded chunks are about the same topic (see test_conflict_detection_service.py
and the live demo) — StubEmbedder's hash-based vectors can't do that. So
here a conflict record is inserted directly against the same DB the API
test client uses, and the test proves the *read* side: listing, document
scoping, and response shape.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.conflict import KnowledgeConflict


def _upload(client: TestClient, headers, filename: str, content: bytes, **form):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
        data=form,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunk_ids(client: TestClient, headers, document_id: str) -> list[str]:
    chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=headers
    ).json()["items"]
    return [c["id"] for c in chunks]


def test_conflicts_empty_by_default(client: TestClient, auth_headers) -> None:
    body = client.get("/api/v1/conflicts", headers=auth_headers).json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_document_conflicts_empty_by_default(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "solo.txt", b"Employees get 20 days leave.")
    body = client.get(f"/api/v1/documents/{doc['id']}/conflicts", headers=auth_headers).json()
    assert body["items"] == []
    assert body["total"] == 0


def test_priority_stored_in_document_metadata(client: TestClient, auth_headers) -> None:
    doc = _upload(
        client, auth_headers, "priority.txt", b"Legal policy content.",
        priority="7", department="Legal",
    )
    fetched = client.get(f"/api/v1/documents/{doc['id']}", headers=auth_headers).json()
    assert fetched["metadata"]["priority"] == 7
    assert fetched["metadata"]["department"] == "Legal"


def test_priority_defaults_to_zero(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "no_priority.txt", b"Ordinary content.")
    fetched = client.get(f"/api/v1/documents/{doc['id']}", headers=auth_headers).json()
    assert fetched["metadata"]["priority"] == 0


def test_conflict_appears_in_list_and_document_endpoints(
    client: TestClient, auth_headers, test_db_engine
) -> None:
    doc_a = _upload(client, auth_headers, "hr_handbook.txt", b"Employees get 20 days leave.", priority="1")
    doc_b = _upload(client, auth_headers, "legal_policy.txt", b"Employees get 25 days leave.", priority="5")
    chunk_a_id = _chunk_ids(client, auth_headers, doc_a["id"])[0]
    chunk_b_id = _chunk_ids(client, auth_headers, doc_b["id"])[0]

    async def insert_conflict() -> None:
        factory = async_sessionmaker(test_db_engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                KnowledgeConflict(
                    claim_a_chunk_id=uuid.UUID(chunk_b_id),
                    claim_a_document_id=uuid.UUID(doc_b["id"]),
                    claim_a_content="Employees get 25 days leave.",
                    claim_b_chunk_id=uuid.UUID(chunk_a_id),
                    claim_b_document_id=uuid.UUID(doc_a["id"]),
                    claim_b_content="Employees get 20 days leave.",
                    contradiction_score=0.97,
                    preferred_chunk_id=uuid.UUID(chunk_b_id),
                    resolved=True,
                    resolution_reason="'legal_policy' has higher document priority (5 > 1)",
                )
            )
            await session.commit()

    asyncio.run(insert_conflict())

    listed = client.get("/api/v1/conflicts", headers=auth_headers).json()
    assert listed["total"] == 1
    item = listed["items"][0]
    assert item["claim_a_chunk_id"] == chunk_b_id
    assert item["claim_b_chunk_id"] == chunk_a_id
    assert item["resolved"] is True
    assert item["preferred_chunk_id"] == chunk_b_id
    assert "priority" in item["resolution_reason"].lower()

    for_a = client.get(f"/api/v1/documents/{doc_a['id']}/conflicts", headers=auth_headers).json()
    assert for_a["total"] == 1
    for_b = client.get(f"/api/v1/documents/{doc_b['id']}/conflicts", headers=auth_headers).json()
    assert for_b["total"] == 1

    other_doc = _upload(client, auth_headers, "unrelated.txt", b"Unrelated content entirely.")
    for_other = client.get(
        f"/api/v1/documents/{other_doc['id']}/conflicts", headers=auth_headers
    ).json()
    assert for_other["total"] == 0
