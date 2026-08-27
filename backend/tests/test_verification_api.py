"""API-level tests for evidence verification (Module 9) through
POST /api/v1/chat/query.
"""

from fastapi.testclient import TestClient

HANDBOOK = (
    b"Employees receive 25 days of paid annual leave per calendar year.\n\n"
    b"Employees receive 10 paid sick days per year."
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


def test_verification_fields_present_and_disabled_by_default(
    client: TestClient, auth_headers
) -> None:
    """conftest.py disables verification (like the reranker) for
    determinism/speed in ordinary API tests; the response shape must
    still carry the Module 9 fields."""
    doc = _upload(client, auth_headers, "handbook.txt", HANDBOOK)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = client.post(
        "/api/v1/chat/query", headers=auth_headers, json={"query": chunk_text}
    ).json()

    assert body["confidence"] is None
    assert body["hallucination_detected"] is None
    assert body["claim_verifications"] == []
    assert body["verification"] == {
        "enabled": False,
        "model": "none",
        "threshold": 0.5,
        "claims_checked": 0,
    }


def test_verification_no_context_answer_is_not_flagged_as_hallucination(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "verification_enabled", True)

    body = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"query": "What is a totally unindexed topic?"},
    ).json()

    assert body["retrieved_chunks"] == 0
    assert body["confidence"] == 1.0
    assert body["hallucination_detected"] is False
    assert body["claim_verifications"] == []


def test_verification_end_to_end_with_real_nli_model_on_extractive_answer(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """Real NLI model, real extractive-generator answer built verbatim
    from the uploaded chunk: this must score as well-grounded, proving
    the pipeline doesn't cry wolf on a genuinely supported answer."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "verification_enabled", True)

    doc = _upload(client, auth_headers, "handbook_verify.txt", HANDBOOK)
    chunk_text = _chunk_texts(client, auth_headers, doc["id"])[0]

    body = client.post(
        "/api/v1/chat/query", headers=auth_headers, json={"query": chunk_text}
    ).json()

    assert body["verification"]["enabled"] is True
    assert body["verification"]["model"] == "cross-encoder/nli-deberta-v3-xsmall"
    assert body["verification"]["claims_checked"] >= 1
    assert body["hallucination_detected"] is False
    assert body["confidence"] > 0.8

    claim = body["claim_verifications"][0]
    assert set(claim) == {
        "claim", "support_score", "supported", "verdict", "source", "version",
        "page", "chunk_id", "cited_markers", "citation_verified",
    }
    assert claim["supported"] is True
    assert claim["source"] == doc["title"]
    assert "⚠" not in body["answer"]
