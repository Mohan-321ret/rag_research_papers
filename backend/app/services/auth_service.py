"""Authentication service: registration, login, token issuance.

Deliberately simple for this research project: a single signed access
token (JWT, because the frontend decodes its ``exp`` claim client-side)
with a long expiry — no refresh tokens, rotation, or server-side token
state.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import create_token, hash_password, verify_password
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserRead

logger = get_logger(__name__)


class AuthService:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        user_repository: UserRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self._settings = settings
        self._session = session
        self._users = user_repository
        self._audit = audit_repository

    async def register(
        self, *, email: str, password: str, full_name: str | None
    ) -> TokenResponse:
        email = email.strip().lower()
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")

        user = await self._users.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )
        await self._audit.record(
            action="user.register", user_id=user.id, resource_type="user",
            resource_id=str(user.id),
        )
        await self._session.commit()
        logger.info("user_registered", user_id=str(user.id))
        return self._token_response(user)

    async def login(self, *, email: str, password: str) -> TokenResponse:
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password")
        if not user.is_active:
            raise UnauthorizedError("This account has been deactivated")

        await self._audit.record(
            action="user.login", user_id=user.id, resource_type="user",
            resource_id=str(user.id),
        )
        await self._session.commit()
        logger.info("user_logged_in", user_id=str(user.id))
        return self._token_response(user)

    def _token_response(self, user: User) -> TokenResponse:
        token = create_token(str(user.id))
        return TokenResponse(
            access_token=token,
            expires_in=self._settings.access_token_expire_minutes * 60,
            user=UserRead.model_validate(user),
        )
