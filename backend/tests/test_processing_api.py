"""Tests for the processing pipeline through the documents API."""

import uuid

from fastapi.testclient import TestClient

ARTICLE = (
    b"1. Introduction\n"
    b"Enterprise knowledge changes constantly and retrieval systems must adapt. "
    b"This document describes the drift-aware architecture in detail.\n\n"
    b"2. Architecture\n"
    b"Documents are versioned, chunked and embedded. Each chunk keeps its "
    b"relationship to the version and document that produced it, enabling "
    b"citations and historical answers over time."
)


def _upload(client: TestClient, headers, filename: str, content: bytes):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_upload_auto_processes_document(client: TestClient, auth_headers) -> None:
    body = _upload(client, auth_headers, "article.txt", ARTICLE).json()

    assert body["status"] == "READY"
    metadata = body["metadata"]
    assert metadata["language"] == "en"
    assert metadata["chunk_count"] >= 1
    assert metadata["embedding_model"] == "stub-embedder"


def test_chunks_endpoint_returns_full_chunk_structure(
    client: TestClient, auth_headers
) -> None:
    document_id = _upload(client, auth_headers, "structured.txt", ARTICLE).json()["id"]

    payload = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=auth_headers
    ).json()

    assert payload["version_number"] == 1
    assert payload["total"] >= 1
    chunk = payload["items"][0]
    # The spec'd chunk structure, including the embedding -> chunk ->
    # version -> document relationship.
    assert chunk["document_id"] == document_id
    assert chunk["version_id"] == payload["version_id"]
    assert chunk["chunk_index"] == 0
    assert chunk["content"]
    assert chunk["embedding_ref"] is not None
    assert chunk["section"] == "Introduction"
    assert chunk["page_number"] == 1
    assert chunk["metadata"]["language"] == "en"
    assert chunk["metadata"]["embedding_model"] == "stub-embedder"
    assert "created_at" in chunk


def test_reprocess_is_idempotent(client: TestClient, auth_headers) -> None:
    document_id = _upload(client, auth_headers, "reproc.txt", ARTICLE).json()["id"]
    first = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=auth_headers
    ).json()

    result = client.post(
        f"/api/v1/documents/{document_id}/process", headers=auth_headers
    ).json()
    assert result["status"] == "READY"
    assert result["chunk_count"] == first["total"]

    second = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=auth_headers
    ).json()
    assert second["total"] == first["total"]

    # Incremental re-indexing (Phase 14): reprocessing unchanged content is
    # a genuine no-op on the index. Every chunk keeps its existing row and
    # vector — nothing is re-embedded, added, or removed. (Before Phase 14
    # this path deleted every vector and rebuilt them, so the refs came
    # back *fresh*; preserving them is the improvement being locked in.)
    assert result["embedded_count"] == 0
    assert result["chunks_reused"] == first["total"]
    assert result["vectors_added"] == 0
    assert result["vectors_removed"] == 0

    old_refs = {c["embedding_ref"] for c in first["items"]}
    new_refs = {c["embedding_ref"] for c in second["items"]}
    assert old_refs == new_refs


def test_old_version_chunks_survive_new_version(client: TestClient, auth_headers) -> None:
    v1_text = b"Remote work policy: everyone may work from home."
    v2_text = b"Remote work policy: hybrid schedule, three days on site."

    document_id = _upload(client, auth_headers, "policy.txt", v1_text).json()["id"]
    _upload(client, auth_headers, "policy.txt", v2_text)

    v1_chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks?version=1", headers=auth_headers
    ).json()
    v2_chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=auth_headers
    ).json()

    assert v1_chunks["version_number"] == 1
    assert v1_chunks["total"] >= 1  # historical chunks kept
    assert v2_chunks["version_number"] == 2
    assert "hybrid" in v2_chunks["items"][0]["content"]
    assert "everyone" in v1_chunks["items"][0]["content"]


def test_process_unknown_document_404(client: TestClient, auth_headers) -> None:
    response = client.post(
        f"/api/v1/documents/{uuid.uuid4()}/process", headers=auth_headers
    )
    assert response.status_code == 404


def test_chunks_unknown_version_404(client: TestClient, auth_headers) -> None:
    document_id = _upload(client, auth_headers, "one.txt", ARTICLE).json()["id"]
    response = client.get(
        f"/api/v1/documents/{document_id}/chunks?version=9", headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_document_removes_vectors(client: TestClient, auth_headers, tmp_path) -> None:
    import faiss

    document_id = _upload(client, auth_headers, "gone.txt", ARTICLE).json()["id"]

    index_file = tmp_path / "vectors" / "index.faiss"
    assert index_file.exists()
    assert faiss.read_index(str(index_file)).ntotal >= 1

    assert (
        client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers).status_code
        == 204
    )
    assert faiss.read_index(str(index_file)).ntotal == 0
