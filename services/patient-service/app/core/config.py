"""Environment-driven configuration with fail-fast, secret-safe validation."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must match the identity service's token contract: HMAC algorithms only, never "none".
MIN_SECRET_BYTES_BY_ALGORITHM: dict[str, int] = {"HS256": 32, "HS384": 48, "HS512": 64}
_PLACEHOLDER_MARKERS = ("replace", "change-me", "changeme", "placeholder", "your-secret", "example")
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    """Raised when configuration is invalid. Messages never contain configuration values."""


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


class DatabaseSettings(BaseSettings):
    """Minimal settings needed by Alembic migrations."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(min_length=1)


class Settings(DatabaseSettings):
    app_name: str = "patient-service"
    app_env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"

    # Verification-only copy of the identity service's key set. This service never issues tokens.
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_key_id: str = Field(default="k1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    jwt_issuer: str = Field(min_length=1)
    jwt_audience: str = Field(min_length=1)
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=120)
    jwt_previous_keys: dict[str, SecretStr] = Field(default_factory=dict)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _LOG_LEVELS:
            raise ValueError(f"must be one of {sorted(_LOG_LEVELS)}")
        return upper

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_algorithm(cls, value: str) -> str:
        upper = value.upper()
        if upper not in MIN_SECRET_BYTES_BY_ALGORITHM:
            raise ValueError(f"must be one of {sorted(MIN_SECRET_BYTES_BY_ALGORITHM)}")
        return upper

    @model_validator(mode="after")
    def _validate_verification_keys(self) -> "Settings":
        min_bytes = MIN_SECRET_BYTES_BY_ALGORITHM[self.jwt_algorithm]
        if self.jwt_key_id in self.jwt_previous_keys:
            raise ValueError("JWT_PREVIOUS_KEYS must not contain the active JWT_KEY_ID")
        keys = {self.jwt_key_id: self.jwt_secret_key, **self.jwt_previous_keys}
        for kid, secret in keys.items():
            raw = secret.get_secret_value()
            if len(raw.encode("utf-8")) < min_bytes:
                raise ValueError(
                    f"JWT verification key '{kid}' must be at least {min_bytes} bytes "
                    f"for {self.jwt_algorithm}"
                )
            if _looks_like_placeholder(raw):
                raise ValueError(
                    f"JWT verification key '{kid}' looks like a placeholder; use the real secret"
                )
        return self

    @property
    def verification_keys(self) -> dict[str, bytes]:
        """All keys accepted for signature verification, keyed by `kid`."""
        keys = {self.jwt_key_id: self.jwt_secret_key, **self.jwt_previous_keys}
        return {kid: secret.get_secret_value().encode("utf-8") for kid, secret in keys.items()}


def _format_errors(exc: ValidationError) -> str:
    # Deliberately excludes `input` so secrets never reach logs or tracebacks.
    parts = []
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(item) for item in error["loc"]) or "settings"
        parts.append(f"{location}: {error['msg']}")
    return "Invalid configuration: " + "; ".join(parts)


def load_settings(**overrides: object) -> Settings:
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise ConfigurationError(_format_errors(exc)) from None


def load_database_settings() -> DatabaseSettings:
    try:
        return DatabaseSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise ConfigurationError(_format_errors(exc)) from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
