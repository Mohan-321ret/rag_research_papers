"""API-level tests for Concept Drift Detection (Phase 12) through
GET /api/v1/documents/{id}/concept-drift.
"""

from fastapi.testclient import TestClient


def _upload(client: TestClient, headers, filename: str, content: bytes):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _concept_drift(client: TestClient, headers, document_id: str):
    response = client.get(
        f"/api/v1/documents/{document_id}/concept-drift", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_concept_drift_disabled_by_default_records_nothing(
    client: TestClient, auth_headers
) -> None:
    doc = _upload(client, auth_headers, "cd_disabled.txt", b"Some initial content.")
    _upload(client, auth_headers, "cd_disabled.txt", b"Some revised content, changed.")

    history = _concept_drift(client, auth_headers, doc["id"])
    assert history["reports"] == []


def test_concept_drift_no_report_for_brand_new_document(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(client, auth_headers, "cd_new.txt", b"Employees receive 25 days of leave.")
    history = _concept_drift(client, auth_headers, doc["id"])
    assert history["reports"] == []  # nothing prior to drift from


def test_concept_drift_catches_the_spec_expansion_example(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """The exact motivating example from the spec: a broadened scope, not
    a contradiction — caught only because the Conflict Detector's
    contradiction-only check (Phase 11) would miss it entirely."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(
        client, auth_headers, "cd_expansion.txt",
        b"Confidential information includes customer records.",
    )
    doc = _upload(
        client, auth_headers, "cd_expansion.txt",
        b"Confidential information includes customer and employee records.",
    )

    history = _concept_drift(client, auth_headers, doc["id"])
    assert len(history["reports"]) == 1
    report = history["reports"][0]
    assert report["old_version_number"] == 1
    assert report["new_version_number"] == 2
    assert len(report["changed_chunks"]) == 1
    chunk = report["changed_chunks"][0]
    assert chunk["drift_type"] == "expansion"
    assert "customer records" in chunk["old_content"]
    assert "customer and employee records" in chunk["new_content"]
    assert report["drift_type"] == "expansion"


def test_concept_drift_catches_the_spec_remote_days_example(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """The spec's "obvious text difference" example, verified through the
    concept drift pipeline too (not just the Phase 11 conflict detector) —
    proving cosine-distance alignment plus NLI classification catches a
    narrow factual change that raw embedding distance alone would miss
    (see the module's docstring for the empirical reason why)."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(
        client, auth_headers, "cd_remote.txt",
        b"Employees can work remotely 2 days per week.",
    )
    doc = _upload(
        client, auth_headers, "cd_remote.txt",
        b"Employees can work remotely 3 days per week.",
    )

    history = _concept_drift(client, auth_headers, doc["id"])
    assert len(history["reports"]) == 1
    chunk = history["reports"][0]["changed_chunks"][0]
    assert chunk["drift_type"] == "contradiction"


def test_concept_drift_response_shape(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(client, auth_headers, "cd_shape.txt", b"Employees get 20 days of leave.")
    doc = _upload(client, auth_headers, "cd_shape.txt", b"Employees get 30 days of leave.")

    history = _concept_drift(client, auth_headers, doc["id"])
    assert history["document_id"] == doc["id"]
    report = history["reports"][0]
    assert set(report) == {
        "id", "old_version_number", "new_version_number", "drift_score",
        "drift_type", "changed_chunks", "created_at",
    }
    chunk = report["changed_chunks"][0]
    assert set(chunk) == {
        "old_chunk_id", "new_chunk_id", "old_content", "new_content",
        "drift_score", "drift_type",
    }
