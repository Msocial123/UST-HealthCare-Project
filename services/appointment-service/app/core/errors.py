"""Domain/application errors mapped to consistent HTTP responses."""

from typing import Any


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, details: Any = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class DomainValidationError(AppError):
    """Business-rule validation failure that cannot be expressed in a request schema."""

    status_code = 422
    code = "validation_error"


class ServiceUnavailableError(AppError):
    """A dependency (e.g. the Scheduling service) could not be reached or returned an unusable response."""

    status_code = 503
    code = "service_unavailable"


FEATURE_DISABLED_MESSAGE = "Appointment booking is currently disabled"


class FeatureDisabledError(AppError):
    """Patient-facing booking endpoints are switched off (APPOINTMENTS_ENABLED=false)."""

    status_code = 503
    code = "feature_disabled"

    def __init__(self, message: str = FEATURE_DISABLED_MESSAGE) -> None:
        super().__init__(message)


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"

    def __init__(self, message: str = "Not authenticated", *, invalid_token: bool = False) -> None:
        challenge = 'Bearer error="invalid_token"' if invalid_token else "Bearer"
        super().__init__(message, headers={"WWW-Authenticate": challenge})


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)
