from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, get_token_service
from app.core.tokens import TokenService
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import ErrorResponse
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange email and password for a short-lived access token",
    responses={401: {"model": ErrorResponse, "description": "Invalid credentials or disabled account"}},
)
def login(
    body: LoginRequest, db: DbSession, token_service: Annotated[TokenService, Depends(get_token_service)]
) -> TokenResponse:
    return AuthService(db, token_service).login(body.email, body.password)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the authenticated user",
    responses={401: {"model": ErrorResponse}},
)
def read_current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
