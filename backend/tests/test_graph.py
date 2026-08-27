"""Tests for entity/topic extraction and the knowledge graph endpoints.

Graph API tests adapt to the environment: with Neo4j reachable they
verify real graph content; without it they verify graceful 503 handling.
"""

import socket

import pytest
from fastapi.testclient import TestClient

from app.modules.processing.entities import extract_entities, extract_topics

# ---- extraction units -----------------------------------------------------


def test_extracts_acronyms_and_terms() -> None:
    text = (
        "The RAG pipeline uses FAISS for vector search. Knowledge Drift is "
        "measured between versions. The FAISS index is rebuilt nightly by "
        "Acme Research."
    )
    entities = extract_entities(text)
    names = {(e.name, e.entity_type) for e in entities}

    assert ("RAG", "acronym") in names
    assert ("FAISS", "acronym") in names
    assert ("Knowledge Drift", "term") in names
    assert ("Acme Research", "term") in names


def test_sentence_starters_are_not_entities() -> None:
    text = "Retrieval is hard. Retrieval needs context."
    names = {e.name for e in extract_entities(text)}
    assert "Retrieval" not in names


def test_extract_topics_filters_stopwords() -> None:
    text = (
        "drift drift drift retrieval retrieval embedding embedding "
        "the the the and and documents"
    )
    topics = extract_topics(text, top_n=3)
    assert topics[0] == "drift"
    assert "the" not in topics
    assert "and" not in topics


# ---- graph API ------------------------------------------------------------

NEO4J_UP = False
try:
    with socket.create_connection(("127.0.0.1", 7687), timeout=1):
        NEO4J_UP = True
except OSError:
    pass

GRAPH_DOC = (
    b"1. Introduction\n"
    b"The DAA system stores knowledge in PostgreSQL, FAISS and Neo4j. "
    b"Drift Detection compares document versions over time.\n\n"
    b"2. Graph Model\n"
    b"Each Document node links to Version nodes, and chunks mention "
    b"entities such as Knowledge Graph structures."
)


def _upload(client: TestClient, headers, filename: str, content: bytes, **form):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
        data=form,
    )


def test_chunks_carry_extracted_entities(client: TestClient, auth_headers) -> None:
    document_id = _upload(client, auth_headers, "graphdoc.txt", GRAPH_DOC).json()["id"]
    chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=auth_headers
    ).json()["items"]

    all_entities = {
        e["name"] for chunk in chunks for e in chunk["metadata"]["entities"]
    }
    assert "DAA" in all_entities or "FAISS" in all_entities
    assert any(e for e in all_entities)


def test_document_metadata_gains_topics(client: TestClient, auth_headers) -> None:
    body = _upload(client, auth_headers, "topics.txt", GRAPH_DOC).json()
    assert isinstance(body["metadata"]["topics"], list)


@pytest.mark.skipif(NEO4J_UP, reason="Neo4j is running; degradation not testable")
def test_graph_endpoints_degrade_to_503_without_neo4j(
    client: TestClient, auth_headers
) -> None:
    document_id = _upload(client, auth_headers, "no-graph.txt", GRAPH_DOC).json()["id"]

    sync = client.post(
        f"/api/v1/graph/documents/{document_id}/sync", headers=auth_headers
    )
    assert sync.status_code == 503
    assert "Neo4j" in sync.json()["detail"]
    assert client.get("/api/v1/graph/stats", headers=auth_headers).status_code == 503


@pytest.mark.skipif(not NEO4J_UP, reason="Neo4j not running")
def test_graph_sync_and_neighborhood(client: TestClient, auth_headers) -> None:
    body = _upload(
        client, auth_headers, "graphful.txt", GRAPH_DOC,
        author="G. Author", department="Research",
    ).json()
    document_id = body["id"]

    sync = client.post(
        f"/api/v1/graph/documents/{document_id}/sync", headers=auth_headers
    )
    assert sync.status_code == 200, sync.text
    counts = sync.json()
    assert counts["versions"] == 1
    assert counts["chunks"] >= 1
    assert counts["entities"] >= 1

    graph = client.get(
        f"/api/v1/graph/documents/{document_id}", headers=auth_headers
    ).json()
    assert graph["title"]
    assert graph["authors"] == ["G. Author"]
    assert graph["departments"] == ["Research"]
    assert graph["versions"][0]["number"] == 1
    assert graph["chunk_count"] >= 1

    stats = client.get("/api/v1/graph/stats", headers=auth_headers).json()
    assert stats["nodes"].get("Document", 0) >= 1
    assert stats["relationships"].get("HAS_VERSION", 0) >= 1

    # Cleanup: deleting the document removes its graph projection too.
    client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
    assert (
        client.get(
            f"/api/v1/graph/documents/{document_id}", headers=auth_headers
        ).status_code
        == 404
    )


@pytest.mark.skipif(not NEO4J_UP, reason="Neo4j not running")
def test_supersedes_chain(client: TestClient, auth_headers) -> None:
    _v1 = _upload(client, auth_headers, "chain.txt", b"Policy first edition covering drift.")
    document_id = _v1.json()["id"]
    _upload(client, auth_headers, "chain.txt", b"Policy second edition covering drift better.")

    sync = client.post(
        f"/api/v1/graph/documents/{document_id}/sync", headers=auth_headers
    ).json()
    assert sync["versions"] == 2

    graph = client.get(
        f"/api/v1/graph/documents/{document_id}", headers=auth_headers
    ).json()
    numbers = [v["number"] for v in graph["versions"]]
    assert numbers == [1, 2]
    assert graph["versions"][1]["is_current"] is True

    stats = client.get("/api/v1/graph/stats", headers=auth_headers).json()
    assert stats["relationships"].get("SUPERSEDES", 0) >= 1

    client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
