"""Tests for the /api/v1/auth endpoints."""

import uuid

from fastapi.testclient import TestClient


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


def _register(client: TestClient, email: str, password: str = "secret-password-1"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )


def test_register_returns_token_and_user(client: TestClient) -> None:
    email = _unique_email()
    response = _register(client, email)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"].count(".") == 2  # JWT shape (frontend decodes exp)
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "USER"


def test_register_duplicate_email_conflict(client: TestClient) -> None:
    email = _unique_email()
    assert _register(client, email).status_code == 201

    response = _register(client, email)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_register_rejects_short_password(client: TestClient) -> None:
    response = _register(client, _unique_email(), password="short")
    assert response.status_code == 422


def test_login_returns_token(client: TestClient) -> None:
    email = _unique_email()
    _register(client, email)

    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret-password-1"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == email


def test_login_wrong_password_unauthorized(client: TestClient) -> None:
    email = _unique_email()
    _register(client, email)

    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password-1"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_me_roundtrip(client: TestClient) -> None:
    email = _unique_email()
    token = _register(client, email).json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_without_token_unauthorized(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_garbage_token_unauthorized(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
