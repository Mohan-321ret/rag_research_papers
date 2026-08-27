"""Tests for the knowledge browsing endpoints (Phase 15):
/knowledge/entities, /relationships, /versions, /drift.
"""

from fastapi.testclient import TestClient

POLICY_V1 = b"1. Annual Leave\nEmployees at Acme Corp receive 20 days of annual leave.\n"
POLICY_V2 = b"1. Annual Leave\nEmployees at Acme Corp receive 30 days of annual leave.\n"


def _upload(client: TestClient, headers, filename: str, content: bytes):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _get(client: TestClient, headers, path: str):
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# NOTE: the test database is session-scoped, so rows from earlier tests are
# still present. These corpus-wide feeds are therefore asserted by *delta*
# or by filtering to the document under test, never by absolute totals.


# ---- entities -----------------------------------------------------------


def test_entities_listed_after_upload(client: TestClient, auth_headers) -> None:
    before = _get(client, auth_headers, "/api/v1/knowledge/entities")["total"]
    doc = _upload(client, auth_headers, "entities.txt", POLICY_V1)
    after = _get(client, auth_headers, "/api/v1/knowledge/entities")

    assert after["total"] > before
    mine = _get(
        client, auth_headers, f"/api/v1/knowledge/entities?document_id={doc['id']}"
    )
    assert mine["total"] >= 1
    entity = mine["items"][0]
    assert set(entity) == {
        "id", "name", "entity_type", "description", "document_id",
        "properties", "created_at",
    }
    assert entity["document_id"] == doc["id"]


def test_entities_filter_by_document(client: TestClient, auth_headers) -> None:
    doc_a = _upload(client, auth_headers, "doc_a.txt", POLICY_V1)
    _upload(client, auth_headers, "doc_b.txt", b"1. Travel\nEconomy class for all trips.\n")

    body = _get(
        client, auth_headers, f"/api/v1/knowledge/entities?document_id={doc_a['id']}"
    )
    assert body["total"] >= 1
    assert {e["document_id"] for e in body["items"]} == {doc_a["id"]}


def test_entities_search_filter(client: TestClient, auth_headers) -> None:
    _upload(client, auth_headers, "acme.txt", POLICY_V1)
    all_entities = _get(client, auth_headers, "/api/v1/knowledge/entities")
    name = all_entities["items"][0]["name"]

    body = _get(client, auth_headers, f"/api/v1/knowledge/entities?search={name}")
    assert body["total"] >= 1
    assert all(name.lower() in e["name"].lower() for e in body["items"])


def test_entities_pagination(client: TestClient, auth_headers) -> None:
    _upload(client, auth_headers, "paged.txt", POLICY_V1)
    body = _get(client, auth_headers, "/api/v1/knowledge/entities?limit=1&offset=0")
    assert len(body["items"]) <= 1
    assert body["limit"] == 1


# ---- relationships ------------------------------------------------------


def test_relationships_endpoint_shape(client: TestClient, auth_headers) -> None:
    """No relationship extraction runs yet (the table is populated by later
    work), so this must return a well-formed empty page rather than error."""
    body = _get(client, auth_headers, "/api/v1/knowledge/relationships")
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["items"] == []
    assert body["total"] == 0


# ---- versions -----------------------------------------------------------


def test_versions_feed_lists_all_versions(client: TestClient, auth_headers) -> None:
    doc = _upload(client, auth_headers, "versioned.txt", POLICY_V1)
    _upload(client, auth_headers, "versioned.txt", POLICY_V2)

    body = _get(client, auth_headers, "/api/v1/knowledge/versions?limit=200")
    mine = [item for item in body["items"] if item["document_id"] == doc["id"]]
    assert {item["version_number"]: item["status"] for item in mine} == {
        1: "deprecated",
        2: "active",
    }
    assert all(item["document_title"] == "versioned" for item in mine)
    # Newest first within this document.
    assert mine[0]["version_number"] == 2


# ---- drift --------------------------------------------------------------


def test_drift_feed_records_nothing_when_evolution_disabled(
    client: TestClient, auth_headers
) -> None:
    before = _get(client, auth_headers, "/api/v1/knowledge/drift")["total"]
    _upload(client, auth_headers, "nodrift.txt", POLICY_V1)
    _upload(client, auth_headers, "nodrift.txt", POLICY_V2)
    after = _get(client, auth_headers, "/api/v1/knowledge/drift")["total"]
    assert after == before


def test_drift_feed_reports_transitions(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)
    doc = _upload(client, auth_headers, "drifty.txt", POLICY_V1)
    _upload(client, auth_headers, "drifty.txt", POLICY_V2)

    body = _get(client, auth_headers, "/api/v1/knowledge/drift?limit=200")
    mine = [item for item in body["items"] if item["document_id"] == doc["id"]]
    assert len(mine) == 2  # "created" + "revised"
    entry = mine[0]
    assert set(entry) == {
        "id", "document_id", "document_title", "from_version_number",
        "to_version_number", "change_type", "text_similarity", "drift_score",
        "drift_magnitude", "has_conflict", "summary", "created_at",
    }
    assert entry["document_title"] == "drifty"
    assert {item["change_type"] for item in mine} == {"created", "revised"}
    assert isinstance(body["summary"], dict)
    assert "with_conflict" in body["summary"]


def test_drift_min_filter(client: TestClient, auth_headers, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "evolution_enabled", True)
    _upload(client, auth_headers, "filtered.txt", POLICY_V1)
    _upload(client, auth_headers, "filtered.txt", POLICY_V2)

    everything = _get(client, auth_headers, "/api/v1/knowledge/drift")
    filtered = _get(client, auth_headers, "/api/v1/knowledge/drift?min_drift=0.99")
    assert filtered["total"] <= everything["total"]
    assert all(item["drift_score"] >= 0.99 for item in filtered["items"])


def test_knowledge_endpoints_require_auth(client: TestClient) -> None:
    for path in ("entities", "relationships", "versions", "drift"):
        assert client.get(f"/api/v1/knowledge/{path}").status_code == 401
