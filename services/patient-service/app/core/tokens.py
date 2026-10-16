"""Local verification of identity-service access tokens (see identity-service README, token contract).

This service only verifies tokens; it never issues them and never calls the identity service at runtime.
"""

import uuid
from dataclasses import dataclass

import jwt

from app.core.config import Settings
from app.domain.roles import Role

TOKEN_USE_ACCESS = "access"  # noqa: S105 (claim value, not a secret)
REQUIRED_CLAIMS = ["iss", "aud", "sub", "iat", "nbf", "exp", "jti"]


class TokenError(Exception):
    """Token is missing, malformed, expired or otherwise untrusted. Message is safe to log."""


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, derived only from a verified token."""

    subject: uuid.UUID
    roles: frozenset[Role]
    token_id: str


class TokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def verify(self, token: str) -> Principal:
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
            roles = frozenset(Role(value) for value in raw_roles)
        except (ValueError, TypeError) as exc:
            raise TokenError("invalid token claims") from exc

        return Principal(subject=subject, roles=roles, token_id=str(payload["jti"]))
