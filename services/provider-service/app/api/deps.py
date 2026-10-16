import logging
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.tokens import Principal, TokenError, TokenVerifier
from app.domain.roles import Permission, has_permission

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False, description="Access token issued by the Identity service")


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_token_verifier(request: Request) -> TokenVerifier:
    return request.app.state.token_verifier


def get_principal(
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


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_permission(permission: Permission) -> Callable[[Principal], Principal]:
    def dependency(principal: CurrentPrincipal) -> Principal:
        if not has_permission(principal.roles, permission):
            logger.info(
                "permission_denied",
                extra={
                    "event": "permission_denied",
                    "subject": str(principal.subject),
                    "permission": permission.value,
                },
            )
            raise PermissionDeniedError()
        return principal

    return dependency
