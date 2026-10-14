import logging

from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError
from app.core.passwords import burn_verification_time, hash_password, needs_rehash, verify_password
from app.core.time import utcnow
from app.core.tokens import TokenService
from app.domain.roles import Role
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS_MESSAGE = "Invalid credentials"


class AuthService:
    def __init__(self, session: Session, token_service: TokenService) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = token_service

    def login(self, email: str, password: str) -> TokenResponse:
        user = self._users.get_by_email(email)
        if user is None:
            burn_verification_time(password)
            logger.info("login_failed", extra={"event": "login_failed", "reason": "unknown_user"})
            raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)
        if not verify_password(user.password_hash, password):
            logger.info(
                "login_failed",
                extra={"event": "login_failed", "reason": "bad_password", "user_id": str(user.id)},
            )
            raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)
        if not user.is_active:
            logger.info(
                "login_failed", extra={"event": "login_failed", "reason": "disabled", "user_id": str(user.id)}
            )
            raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = utcnow()
        self._session.commit()

        issued = self._tokens.issue_access_token(user.id, Role(user.role))
        logger.info("login_succeeded", extra={"event": "login_succeeded", "user_id": str(user.id)})
        return TokenResponse(access_token=issued.token, expires_in=issued.expires_in)
