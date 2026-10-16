"""Reusable FastAPI dependencies for database sessions, authentication and authorization."""

import logging
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.tokens import Principal, TokenError, TokenVerifier
from app.domain.roles import Permission, permissions_for

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(
    auto_error=False,
    description=(
        "Identity-service access token (POST /api/v1/auth/login), sent as `Authorization: Bearer <token>`."
    ),
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_token_verifier(request: Request) -> TokenVerifier:
    return request.app.state.token_verifier


DbSession = Annotated[Session, Depends(get_db)]


def get_current_principal(
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Not authenticated")
    try:
        return verifier.verify(credentials.credentials)
    except TokenError as exc:
        logger.info("token_rejected", extra={"event": "token_rejected", "reason": str(exc)})
        raise AuthenticationError("Invalid or expired token", invalid_token=True) from None


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_permission(*permissions: Permission) -> Callable[[Principal], Principal]:
    """Dependency factory: allow only callers whose token roles grant all `permissions` (403 otherwise)."""
    required = frozenset(permissions)

    def dependency(principal: CurrentPrincipal) -> Principal:
        if not required <= permissions_for(principal.roles):
            raise PermissionDeniedError()
        return principal

    return dependency
