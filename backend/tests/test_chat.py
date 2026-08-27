"""Tests for POST /api/v1/chat/query (baseline RAG)."""

from fastapi.testclient import TestClient

DOC = (
    b"1. Leave Policy\n"
    b"Employees receive 25 days of paid annual leave per year. Unused days "
    b"can be carried over until March of the following year.\n\n"
    b"2. Remote Work\n"
    b"Hybrid schedule with at least two days in the office per week."
)


def _upload(client: TestClient, headers, filename: str, content: bytes):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunk_texts(client: TestClient, headers, document_id: str) -> list[str]:
    chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=headers
    ).json()["items"]
    return [c["content"] for c in chunks]


def test_query_returns_grounded_answer_with_citations(
    client: TestClient, auth_headers
) -> None:
    doc = _upload(client, auth_headers, "policy.txt", DOC)
    # The stub embedder is deterministic: identical text -> identical vector,
    # so querying with a chunk's own text guarantees an exact top-1 match.
    leave_chunk = _chunk_texts(client, auth_headers, doc["id"])[0]

    response = client.post(
        "/api/v1/chat/query", headers=auth_headers, json={"query": leave_chunk}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["answer"]
    assert body["model"] == "extractive-baseline"
    assert body["retrieved_chunks"] >= 1
    assert body["query_id"] and body["answer_id"]

    top = body["citations"][0]
    assert top["marker"] == 1
    assert top["document_id"] == doc["id"]
    assert top["document_name"] == doc["title"]
    assert top["score"] > 0.99  # exact vector match
    assert top["chunk_id"]
    assert "page" in top
    assert top["snippet"]
    # The extractive answer cites the block it drew from.
    assert "[1]" in body["answer"]


def test_query_with_empty_knowledge_base(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"query": "What is the leave policy?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retrieved_chunks"] == 0
    assert body["citations"] == []
    assert "could not find" in body["answer"].lower()


def test_query_respects_top_k(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "topk.txt", DOC)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"query": chunk_text, "top_k": 1},
    ).json()
    assert len(body["citations"]) <= 1


def test_query_ignores_superseded_versions(client: TestClient, auth_headers) -> None:
    _upload(client, auth_headers, "versioned.txt", b"Old policy: 20 vacation days total.")
    doc = _upload(client, auth_headers, "versioned.txt", b"New policy: 30 vacation days total.")

    new_chunk = _chunk_texts(client, auth_headers, doc["id"])[0]
    body = client.post(
        "/api/v1/chat/query", headers=auth_headers, json={"query": new_chunk}
    ).json()

    snippets = " ".join(c["snippet"] for c in body["citations"])
    assert "30 vacation days" in snippets
    assert "20 vacation days" not in snippets


def test_query_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/chat/query", json={"query": "hello"})
    assert response.status_code == 401


def test_empty_query_rejected(client: TestClient, auth_headers) -> None:
    response = client.post("/api/v1/chat/query", headers=auth_headers, json={"query": ""})
    assert response.status_code == 422
