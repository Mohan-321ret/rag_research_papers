"""API-level tests for context fusion (Module 7) through
POST /api/v1/chat/query — dedup, compression, and the context_fusion
transparency field, wired end-to-end behind the retrieval router.
"""

from fastapi.testclient import TestClient

HANDBOOK = (
    b"1. Annual Leave Policy\n"
    b"Employees receive 25 days of paid annual leave per calendar year. "
    b"Unused days may be carried over into the first quarter.\n\n"
    b"2. Sick Leave\n"
    b"Employees receive 10 paid sick days per year.\n\n"
    b"3. Remote Work\n"
    b"Hybrid schedule with at least two office days per week.\n\n"
    b"4. Parental Leave\n"
    b"Primary caregivers receive 16 weeks of paid leave."
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


def _query(client: TestClient, headers, text: str, top_k: int | None = None):
    body = {"query": text}
    if top_k is not None:
        body["top_k"] = top_k
    response = client.post("/api/v1/chat/query", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_context_fusion_field_present_and_consistent(
    client: TestClient, auth_headers
) -> None:
    doc = _upload(client, auth_headers, "handbook.txt", HANDBOOK)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = _query(client, auth_headers, chunk_text)
    fusion = body["context_fusion"]

    assert set(fusion) == {
        "candidates", "after_dedup", "final_count", "reranker_model", "conflicts",
    }
    assert fusion["candidates"] >= fusion["after_dedup"] >= fusion["final_count"]
    assert fusion["final_count"] == body["retrieved_chunks"] == len(body["citations"])
    assert fusion["reranker_model"] == "none"  # passthrough in tests (see conftest)
    assert fusion["conflicts"] == []  # conflict detection disabled by default in tests


def test_citations_carry_version_field(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "versioned.txt", b"Draft policy text version one.")
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = _query(client, auth_headers, chunk_text)
    assert body["citations"][0]["version"] == 1


def test_final_context_respects_requested_top_k(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "handbook2.txt", HANDBOOK)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = _query(client, auth_headers, chunk_text, top_k=2)
    assert len(body["citations"]) <= 2
    assert body["context_fusion"]["final_count"] <= 2


def test_citations_have_no_duplicate_chunks(client: TestClient, auth_headers) -> None:
    """The core Module 7 requirement: a chunk found by multiple retrievers
    (or matched twice for any other reason) appears only once in the
    final, fused citation list."""
    doc = _upload(client, auth_headers, "handbook3.txt", HANDBOOK)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = _query(client, auth_headers, chunk_text, top_k=8)
    chunk_ids = [c["chunk_id"] for c in body["citations"]]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_empty_knowledge_base_context_fusion_is_empty(
    client: TestClient, auth_headers
) -> None:
    body = _query(client, auth_headers, "What is a totally unindexed topic?")
    assert body["context_fusion"] == {
        "candidates": 0,
        "after_dedup": 0,
        "final_count": 0,
        "reranker_model": "none",
        "conflicts": [],
    }
