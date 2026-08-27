"""Tests for GET /chat/history (Phase 15)."""

import uuid as _uuid

from fastapi.testclient import TestClient

DOC = b"1. Leave Policy\nEmployees receive 25 days of paid annual leave per year.\n"


def _fresh_headers(client: TestClient) -> dict[str, str]:
    """A second, independent account — history must be per-user."""
    email = f"other-{_uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret-password-1", "full_name": "Other"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_history_empty_for_new_user(client: TestClient, auth_headers) -> None:
    body = client.get("/api/v1/chat/history", headers=auth_headers).json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_history_records_a_query_and_answer(client: TestClient, auth_headers) -> None:
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("hist.txt", DOC, "text/plain")},
    )
    response = client.post(
        "/api/v1/chat/query", headers=auth_headers, json={"query": "How many leave days?"}
    )
    assert response.status_code == 200, response.text
    answer_id = response.json()["answer_id"]

    body = client.get("/api/v1/chat/history", headers=auth_headers).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert set(item) == {"query_id", "query_text", "intent", "created_at", "answers"}
    assert item["query_text"] == "How many leave days?"

    assert len(item["answers"]) == 1
    answer = item["answers"][0]
    assert set(answer) == {
        "id", "answer_text", "model", "latency_ms", "grounded",
        "confidence", "created_at", "citations",
    }
    assert answer["id"] == answer_id
    assert answer["answer_text"]


def test_history_is_newest_first(client: TestClient, auth_headers) -> None:
    for text in ("first question", "second question", "third question"):
        client.post("/api/v1/chat/query", headers=auth_headers, json={"query": text})

    body = client.get("/api/v1/chat/history", headers=auth_headers).json()
    assert body["total"] == 3
    assert {item["query_text"] for item in body["items"]} == {
        "first question",
        "second question",
        "third question",
    }
    # Assert the ordering *property* rather than an exact sequence: SQLite's
    # CURRENT_TIMESTAMP is second-resolution, so queries issued inside one
    # test share a timestamp and their relative order is decided by the id
    # tiebreak. Descending-by-timestamp still has to hold.
    timestamps = [item["created_at"] for item in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_history_is_scoped_to_the_caller(client: TestClient, auth_headers) -> None:
    """One user's questions must never leak into another's history."""
    client.post("/api/v1/chat/query", headers=auth_headers, json={"query": "mine only"})

    other = _fresh_headers(client)
    other_body = client.get("/api/v1/chat/history", headers=other).json()
    assert other_body["total"] == 0

    client.post("/api/v1/chat/query", headers=other, json={"query": "theirs only"})
    mine = client.get("/api/v1/chat/history", headers=auth_headers).json()
    assert [item["query_text"] for item in mine["items"]] == ["mine only"]


def test_history_pagination(client: TestClient, auth_headers) -> None:
    for i in range(3):
        client.post("/api/v1/chat/query", headers=auth_headers, json={"query": f"q{i}"})

    page = client.get("/api/v1/chat/history?limit=2&offset=0", headers=auth_headers).json()
    assert len(page["items"]) == 2
    assert page["total"] == 3
    assert page["limit"] == 2

    second = client.get("/api/v1/chat/history?limit=2&offset=2", headers=auth_headers).json()
    assert len(second["items"]) == 1
    # No overlap between pages.
    assert {i["query_id"] for i in page["items"]}.isdisjoint(
        {i["query_id"] for i in second["items"]}
    )


def test_history_includes_citations(client: TestClient, auth_headers) -> None:
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("cited.txt", DOC, "text/plain")},
    )
    chunk = client.get(
        f"/api/v1/documents/{upload.json()['id']}/chunks", headers=auth_headers
    ).json()["items"][0]["content"]
    client.post("/api/v1/chat/query", headers=auth_headers, json={"query": chunk})

    body = client.get("/api/v1/chat/history", headers=auth_headers).json()
    citations = body["items"][0]["answers"][0]["citations"]
    assert len(citations) >= 1
    assert set(citations[0]) == {"marker", "chunk_id", "snippet"}
    assert [c["marker"] for c in citations] == sorted(c["marker"] for c in citations)


def test_history_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/chat/history").status_code == 401
