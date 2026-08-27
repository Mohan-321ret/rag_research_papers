"""Tests for POST /feedback (Phase 15)."""

import uuid

from fastapi.testclient import TestClient

DOC = b"1. Leave Policy\nEmployees receive 25 days of paid annual leave per year.\n"


def _answer_id(client: TestClient, headers) -> str:
    """Run a real query so there is a genuine answer row to rate."""
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("fb.txt", DOC, "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    chunk = client.get(
        f"/api/v1/documents/{upload.json()['id']}/chunks", headers=headers
    ).json()["items"][0]["content"]

    query = client.post("/api/v1/chat/query", headers=headers, json={"query": chunk})
    assert query.status_code == 200, query.text
    return query.json()["answer_id"]


def test_submit_feedback(client: TestClient, auth_headers) -> None:
    answer_id = _answer_id(client, auth_headers)

    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers,
        json={"answer_id": answer_id, "rating": "HELPFUL", "comment": "Spot on."},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert set(body) == {"id", "answer_id", "user_id", "rating", "comment", "created_at"}
    assert body["answer_id"] == answer_id
    assert body["rating"] == "HELPFUL"
    assert body["comment"] == "Spot on."
    assert body["user_id"]


def test_feedback_without_comment(client: TestClient, auth_headers) -> None:
    answer_id = _answer_id(client, auth_headers)
    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers,
        json={"answer_id": answer_id, "rating": "NOT_HELPFUL"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["comment"] is None


def test_feedback_unknown_answer_is_404(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers,
        json={"answer_id": str(uuid.uuid4()), "rating": "HELPFUL"},
    )
    assert response.status_code == 404


def test_feedback_invalid_rating_rejected(client: TestClient, auth_headers) -> None:
    answer_id = _answer_id(client, auth_headers)
    response = client.post(
        "/api/v1/feedback",
        headers=auth_headers,
        json={"answer_id": answer_id, "rating": "AMAZING"},
    )
    assert response.status_code == 422


def test_feedback_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/feedback",
        json={"answer_id": str(uuid.uuid4()), "rating": "HELPFUL"},
    )
    assert response.status_code == 401


def test_feedback_shows_up_in_analytics(client: TestClient, auth_headers) -> None:
    """Feedback is the Module 10 signal — it must actually reach the
    aggregates, not just land in a table nothing reads."""
    before = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    before_helpful = before["usage"]["feedback_by_rating"].get("HELPFUL", 0)

    answer_id = _answer_id(client, auth_headers)
    client.post(
        "/api/v1/feedback",
        headers=auth_headers,
        json={"answer_id": answer_id, "rating": "HELPFUL"},
    )

    after = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert after["usage"]["feedback_by_rating"]["HELPFUL"] == before_helpful + 1
