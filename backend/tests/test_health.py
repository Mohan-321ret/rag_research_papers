"""Tests for GET /api/v1/health."""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_reports_service_metadata(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()

    assert body["status"] in {"ok", "degraded"}
    assert body["app"]
    assert body["version"]
    assert "timestamp" in body


def test_health_reports_component_statuses(client: TestClient) -> None:
    components = client.get("/api/v1/health").json()["components"]

    assert set(components) == {"database", "graph_database"}
    for component in components.values():
        assert component["status"] in {"up", "down"}


def test_health_echoes_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-123"})
    assert response.headers["X-Request-ID"] == "test-123"
