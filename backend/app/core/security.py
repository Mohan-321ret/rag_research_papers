"""JWT authentication foundation: token creation/validation, password hashing.

This module provides the primitives that later phases (user accounts,
protected endpoints) will build on. No routes use it yet in Phase 0.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError

TokenType = Literal["access", "refresh"]


def create_token(
    subject: str,
    token_type: TokenType = "access",
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT for the given subject (e.g. user id)."""
    settings = get_settings()
    if expires_delta is None:
        minutes = (
            settings.access_token_expire_minutes
            if token_type == "access"
            else settings.refresh_token_expire_minutes
        )
        expires_delta = timedelta(minutes=minutes)

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: TokenType = "access") -> dict[str, Any]:
    """Decode and validate a JWT, raising ``UnauthorizedError`` on failure."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError(f"Expected a {expected_type} token")
    return payload


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
