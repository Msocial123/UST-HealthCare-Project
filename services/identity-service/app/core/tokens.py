"""JWT access-token issuance and verification (the contract other services implement)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.roles import Role

TOKEN_USE_ACCESS = "access"  # noqa: S105 (claim value, not a secret)
REQUIRED_CLAIMS = ["iss", "aud", "sub", "iat", "nbf", "exp", "jti"]


class TokenError(Exception):
    """Token is missing, malformed, expired or otherwise untrusted. Message is safe to log."""


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: uuid.UUID
    roles: tuple[Role, ...]
    token_id: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_in: int


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def issue_access_token(
        self, user_id: uuid.UUID, role: Role, *, now: datetime | None = None
    ) -> IssuedToken:
        settings = self._settings
        issued_at = now or utcnow()
        lifetime = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        payload = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": str(user_id),
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
            "exp": int((issued_at + lifetime).timestamp()),
            "jti": str(uuid.uuid4()),
            "token_use": TOKEN_USE_ACCESS,
            "roles": [Role(role).value],
        }
        token = jwt.encode(
            payload,
            settings.signing_key,
            algorithm=settings.jwt_algorithm,
            headers={"kid": settings.jwt_key_id, "typ": "JWT"},
        )
        return IssuedToken(token=token, expires_in=int(lifetime.total_seconds()))

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        settings = self._settings
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenError("malformed token") from exc

        if header.get("alg") != settings.jwt_algorithm:
            raise TokenError("unexpected signing algorithm")
        key = settings.verification_keys.get(str(header.get("kid")))
        if key is None:
            raise TokenError("unknown signing key")

        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[settings.jwt_algorithm],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                leeway=settings.jwt_leeway_seconds,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("token expired") from exc
        except jwt.PyJWTError as exc:
            raise TokenError("token verification failed") from exc

        if payload.get("token_use") != TOKEN_USE_ACCESS:
            raise TokenError("not an access token")
        try:
            subject = uuid.UUID(str(payload["sub"]))
            raw_roles = payload.get("roles")
            if not isinstance(raw_roles, list) or not raw_roles:
                raise ValueError("roles must be a non-empty list")
            roles = tuple(Role(value) for value in raw_roles)
        except (ValueError, TypeError) as exc:
            raise TokenError("invalid token claims") from exc

        return AccessTokenClaims(
            subject=subject,
            roles=roles,
            token_id=str(payload["jti"]),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=utcnow().tzinfo),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=utcnow().tzinfo),
        )
