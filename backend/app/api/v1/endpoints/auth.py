"""Authentication endpoints. All logic lives in AuthService."""

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentUserDep
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def register(payload: RegisterRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.register(
        email=payload.email, password=payload.password, full_name=payload.full_name
    )


@router.post("/login", response_model=TokenResponse, summary="Sign in")
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(email=payload.email, password=payload.password)


@router.get("/me", response_model=UserRead, summary="Current user")
async def me(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)
