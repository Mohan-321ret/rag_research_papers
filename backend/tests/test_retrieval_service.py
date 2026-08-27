"""API-level tests for adaptive retrieval (Module 6): routing end-to-end
through POST /api/v1/chat/query.

BM25 reads directly from the (test-session-shared) database rather than a
per-test-isolated store, so these tests use content unlikely to collide
with other tests' fixtures (unique identifiers, distinctive phrasing) and
assert on specific matches rather than corpus-wide counts.
"""

import uuid

from fastapi.testclient import TestClient

CONCEPTUAL_DOC = (
    b"1. Wellbeing Philosophy\n"
    b"Our approach to employee wellbeing centers on flexible schedules, "
    b"mental health support, and psychological safety across teams."
)

# Short and simple enough that querying with its own text still routes to
# VECTOR (no length/entity-count complexity trigger) — needed because the
# stub embedder (see conftest) is hash-based, not semantic: only a query
# identical to an indexed chunk is guaranteed to score above the retrieval
# threshold.
SIMPLE_VECTOR_DOC = b"Our wellbeing philosophy covers flexible schedules."


def _upload(client: TestClient, headers, filename: str, content: bytes, **form):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
        data=form,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _query(client: TestClient, headers, text: str, top_k: int | None = None):
    body = {"query": text}
    if top_k is not None:
        body["top_k"] = top_k
    response = client.post("/api/v1/chat/query", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _chunk_texts(client: TestClient, headers, document_id: str) -> list[str]:
    chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=headers
    ).json()["items"]
    return [c["content"] for c in chunks]


# ---- BM25 route ------------------------------------------------------------


def test_exact_id_query_routes_to_bm25_and_finds_it(
    client: TestClient, auth_headers
) -> None:
    # ID_PATTERN requires an all-digit suffix (e.g. "POL-123"); a random
    # 6-digit number keeps this globally unique without hex letters.
    code = f"POL-{uuid.uuid4().int % 1_000_000:06d}"
    doc = _upload(
        client, auth_headers, "policy_code.txt",
        f"Security incidents must be reported within 24 hours per policy {code}.".encode(),
    )

    body = _query(client, auth_headers, f"What does policy {code} require?")

    assert body["retrieval"]["route"] == "bm25"
    assert body["citations"]
    assert body["citations"][0]["document_id"] == doc["id"]
    assert "bm25" in body["citations"][0]["retrievers"]


def test_clause_reference_routes_to_bm25(client: TestClient, auth_headers) -> None:
    marker = uuid.uuid4().hex[:8]
    _upload(
        client, auth_headers, f"clauses_{marker}.txt",
        f"Section 9.3 ({marker}) covers expense reimbursement timelines.".encode(),
    )

    body = _query(client, auth_headers, f"What is in Section 9.3 ({marker})?")
    assert body["retrieval"]["route"] == "bm25"


# ---- vector route (default / conceptual) -----------------------------------


def test_conceptual_query_routes_to_vector(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "wellbeing.txt", SIMPLE_VECTOR_DOC)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = _query(client, auth_headers, chunk_text)
    assert body["retrieval"]["route"] == "vector"
    assert body["citations"]
    assert body["citations"][0]["document_id"] == doc["id"]
    assert "vector" in body["citations"][0]["retrievers"]


# ---- graph route -------------------------------------------------------


RELATIONSHIP_DOC = (
    b"Our wellbeing philosophy is related to psychological safety practices "
    b"across teams."
)


def test_relationship_query_falls_back_when_graph_empty(
    client: TestClient, auth_headers
) -> None:
    """Graph-auto-sync is off in tests, so no chunks are in Neo4j yet —
    the graph route should degrade to a vector fallback rather than
    return nothing.

    The stub embedder (see conftest) is hash-based, not semantic, so it
    only guarantees a vector match for text identical to an indexed
    chunk — query with the chunk's own content, which still contains
    "related to" and so still triggers the graph route.
    """
    doc = _upload(client, auth_headers, "relations.txt", RELATIONSHIP_DOC)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = _query(client, auth_headers, chunk_text)
    assert body["retrieval"]["route"] == "graph"
    assert body["retrieval"]["fallback_used"] is True
    # Fallback still finds relevant content via vector search.
    assert body["citations"]
    assert body["citations"][0]["document_id"] == doc["id"]


# ---- hybrid route -----------------------------------------------------


def test_complex_query_routes_to_hybrid(client: TestClient, auth_headers) -> None:
    _upload(client, auth_headers, "hybrid_a.txt", CONCEPTUAL_DOC)
    _upload(
        client, auth_headers, "hybrid_b.txt",
        b"2. Compensation\nBase salary reviews happen annually every March.",
    )

    body = _query(
        client,
        auth_headers,
        "Compare our wellbeing philosophy and compensation approach and explain "
        "why both matter for retention across departments over multiple years",
    )
    assert body["retrieval"]["route"] == "hybrid"
    assert set(body["retrieval"]["retriever_hits"]) >= {"vector", "bm25", "graph"}


# ---- response shape / analysis integration -----------------------------


def test_retrieval_info_present_on_every_response(client: TestClient, auth_headers) -> None:
    body = _query(client, auth_headers, "What is the leave policy?")
    assert set(body["retrieval"]) == {
        "route", "reasons", "retriever_hits", "fallback_used", "as_of",
    }
    assert body["retrieval"]["as_of"] is None  # no temporal intent in this query
    assert body["retrieval"]["reasons"]


def test_empty_knowledge_base_vector_route_no_fallback_needed(
    client: TestClient, auth_headers
) -> None:
    body = _query(client, auth_headers, "What is a completely novel unindexed topic?")
    assert body["retrieval"]["route"] == "vector"
    assert body["retrieved_chunks"] == 0
