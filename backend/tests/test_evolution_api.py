"""API-level tests for knowledge evolution (Module 3) through document
upload/versioning and GET /api/v1/documents/{id}/evolution.
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


def _evolution(client: TestClient, headers, document_id: str):
    response = client.get(f"/api/v1/documents/{document_id}/evolution", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _versions(client: TestClient, headers, document_id: str):
    response = client.get(f"/api/v1/documents/{document_id}/versions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_version_status_reflects_current_and_deprecated(
    client: TestClient, auth_headers
) -> None:
    doc = _upload(client, auth_headers, "policy.txt", b"Version one content.")
    doc = _upload(client, auth_headers, "policy.txt", b"Version two, different content.")
    assert doc["new_version_created"] is True

    versions = _versions(client, auth_headers, doc["id"])
    assert len(versions) == 2
    by_number = {v["version_number"]: v for v in versions}
    assert by_number[1]["status"] == "deprecated"
    assert by_number[1]["is_current"] is False
    assert by_number[2]["status"] == "active"
    assert by_number[2]["is_current"] is True


def test_evolution_disabled_by_default_records_nothing(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "disabled.txt", b"Some content for a disabled test.")
    _upload(client, auth_headers, "disabled.txt", b"Some revised content for a disabled test.")

    history = _evolution(client, auth_headers, doc["id"])
    assert history["comparisons"] == []


def test_evolution_records_new_document_creation(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(client, auth_headers, "brandnew.txt", b"Employees receive 25 days of leave.")

    history = _evolution(client, auth_headers, doc["id"])
    assert len(history["comparisons"]) == 1
    comparison = history["comparisons"][0]
    assert comparison["change_type"] == "created"
    assert comparison["from_version_number"] is None
    assert comparison["to_version_number"] == 1
    assert comparison["added_count"] >= 1
    assert comparison["has_conflict"] is False


def test_evolution_records_revision_diff_and_conflict(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    """The exact demo scenario: a real policy value change (20 -> 30 days)
    must show up as a diff *and* be caught as a semantic conflict — the
    Conflict Detector reusing Module 9's NLI model, not just text diffing."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(
        client, auth_headers, "leave_policy.txt",
        b"Employees receive 20 days of paid annual leave per year.",
    )
    doc = _upload(
        client, auth_headers, "leave_policy.txt",
        b"Employees receive 30 days of paid annual leave per year.",
    )
    assert doc["new_version_created"] is True

    history = _evolution(client, auth_headers, doc["id"])
    assert len(history["comparisons"]) == 2  # v1 "created" + v2 "revised"

    revised = next(c for c in history["comparisons"] if c["change_type"] == "revised")
    assert revised["from_version_number"] == 1
    assert revised["to_version_number"] == 2
    assert revised["replaced_count"] >= 1
    assert revised["has_conflict"] is True
    assert len(revised["conflicts"]) >= 1
    conflict = revised["conflicts"][0]
    assert "20 days" in conflict["old_sentence"]
    assert "30 days" in conflict["new_sentence"]
    assert conflict["contradiction_score"] > 0.5
    assert "conflict" in revised["summary"].lower()


def test_evolution_history_ordered_by_version(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(client, auth_headers, "ordered.txt", b"First content revision.")
    doc = _upload(client, auth_headers, "ordered.txt", b"Second content revision, changed.")
    doc = _upload(client, auth_headers, "ordered.txt", b"Third content revision, changed again.")

    history = _evolution(client, auth_headers, doc["id"])
    numbers = [c["to_version_number"] for c in history["comparisons"]]
    assert numbers == sorted(numbers)
    assert numbers == [1, 2, 3]


def test_evolution_response_shape(client: TestClient, auth_headers, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)

    doc = _upload(client, auth_headers, "shape.txt", b"Some content to check the response shape.")
    history = _evolution(client, auth_headers, doc["id"])

    assert history["document_id"] == doc["id"]
    comparison = history["comparisons"][0]
    assert set(comparison) == {
        "id", "from_version_number", "to_version_number", "change_type",
        "text_similarity", "added_count", "removed_count", "replaced_count",
        "added_sentences", "removed_sentences", "drift_score", "drift_magnitude",
        "conflicts", "has_conflict", "vectors_added", "graph_synced", "summary",
        "created_at",
    }
