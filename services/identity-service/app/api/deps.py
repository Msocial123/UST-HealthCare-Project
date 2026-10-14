"""Reusable FastAPI dependencies for database sessions, authentication and authorization."""

import logging
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.tokens import TokenError, TokenService
from app.domain.roles import Permission, Role, has_permission
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access token from POST /api/v1/auth/login, sent as `Authorization: Bearer <token>`.",
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    token_service: Annotated[TokenService, Depends(get_token_service)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Not authenticated")
    try:
        claims = token_service.decode_access_token(credentials.credentials)
    except TokenError as exc:
        logger.info("token_rejected", extra={"event": "token_rejected", "reason": str(exc)})
        raise AuthenticationError("Invalid or expired token", invalid_token=True) from None

    # The identity service re-checks the account so disabled users lose access immediately here.
    user = UserRepository(db).get_by_id(claims.subject)
    if user is None or not user.is_active:
        logger.info("token_rejected", extra={"event": "token_rejected", "reason": "inactive_or_unknown_user"})
        raise AuthenticationError("Invalid or expired token", invalid_token=True)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Dependency factory: allow only users holding one of `roles` (403 otherwise)."""
    allowed = frozenset(roles)

    def dependency(user: CurrentUser) -> User:
        if Role(user.role) not in allowed:
            raise PermissionDeniedError()
        return user

    return dependency


def require_permission(*permissions: Permission) -> Callable[[User], User]:
    """Dependency factory: allow only users whose role grants all `permissions` (403 otherwise)."""

    def dependency(user: CurrentUser) -> User:
        role = Role(user.role)
        if not all(has_permission(role, permission) for permission in permissions):
            raise PermissionDeniedError()
        return user

    return dependency
