"""Tests for the explicit search endpoints (Phase 15):
POST /search/semantic and POST /search/hybrid.
"""

from fastapi.testclient import TestClient

HANDBOOK = (
    b"1. Annual Leave\nEmployees receive 25 days of paid annual leave per year.\n\n"
    b"2. Sick Leave\nEmployees receive 10 paid sick days per year.\n\n"
    b"3. Remote Work\nHybrid schedule with two office days per week.\n"
)


def _upload(client: TestClient, headers, filename: str, content: bytes):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunk_texts(client: TestClient, headers, document_id: str) -> list[str]:
    return [
        c["content"]
        for c in client.get(
            f"/api/v1/documents/{document_id}/chunks", headers=headers
        ).json()["items"]
    ]


def test_semantic_search_returns_ranked_evidence(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "search.txt", HANDBOOK)
    # The stub embedder is hash-based: query with a chunk's exact text so the
    # top-1 match is guaranteed (see conftest).
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    response = client.post(
        "/api/v1/search/semantic", headers=auth_headers, json={"query": chunk_text}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["route"] == "vector"
    assert body["total"] >= 1
    hit = body["results"][0]
    assert set(hit) == {
        "chunk_id", "document_id", "document_name", "version", "page",
        "section", "score", "snippet", "retrievers",
    }
    assert hit["document_id"] == doc["id"]
    assert hit["snippet"]


def test_semantic_search_pins_the_vector_route(client: TestClient, auth_headers) -> None:
    """A short keyword query would normally route to BM25; /search/semantic
    must override the adaptive router."""
    _upload(client, auth_headers, "route.txt", HANDBOOK)
    body = client.post(
        "/api/v1/search/semantic", headers=auth_headers, json={"query": "leave"}
    ).json()
    assert body["route"] == "vector"
    assert any("explicitly requested" in reason for reason in body["reasons"])


def test_hybrid_search_pins_the_hybrid_route(client: TestClient, auth_headers) -> None:
    _upload(client, auth_headers, "hybrid.txt", HANDBOOK)
    body = client.post(
        "/api/v1/search/hybrid", headers=auth_headers, json={"query": "annual leave"}
    ).json()
    assert body["route"] == "hybrid"
    # Hybrid runs every retriever, not just one.
    assert set(body["retriever_hits"]) >= {"vector", "bm25", "graph"}


def test_search_respects_top_k(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "topk.txt", HANDBOOK)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]
    body = client.post(
        "/api/v1/search/hybrid",
        headers=auth_headers,
        json={"query": chunk_text, "top_k": 1},
    ).json()
    assert len(body["results"]) <= 1


def test_search_empty_corpus_returns_no_results(client: TestClient, auth_headers) -> None:
    body = client.post(
        "/api/v1/search/semantic",
        headers=auth_headers,
        json={"query": "nothing has been indexed yet"},
    ).json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/search/semantic", json={"query": "x"}).status_code == 401
    assert client.post("/api/v1/search/hybrid", json={"query": "x"}).status_code == 401


def test_search_rejects_empty_query(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/api/v1/search/semantic", headers=auth_headers, json={"query": ""}
    )
    assert response.status_code == 422
