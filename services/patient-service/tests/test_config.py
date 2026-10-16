import pytest

from app.core.config import ConfigurationError, load_settings
from tests.conftest import TEST_AUDIENCE, TEST_ISSUER, TEST_SECRET

BASE = {
    "_env_file": None,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret_key": TEST_SECRET,
    "jwt_issuer": TEST_ISSUER,
    "jwt_audience": TEST_AUDIENCE,
}


def _load(**overrides: object):
    return load_settings(**{**BASE, **overrides})


def test_valid_settings_load() -> None:
    settings = _load()
    assert settings.jwt_algorithm == "HS256"
    assert settings.verification_keys == {"k1": TEST_SECRET.encode()}


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"jwt_secret_key": "too-short"}, "at least 32 bytes"),
        ({"jwt_secret_key": "REPLACE_WITH_IDENTITY_SERVICE_JWT_SECRET" + "x" * 20}, "placeholder"),
        ({"jwt_algorithm": "none"}, "jwt_algorithm"),
        ({"jwt_algorithm": "RS256"}, "jwt_algorithm"),
        ({"jwt_algorithm": "HS384", "jwt_secret_key": "k" * 40}, "at least 48 bytes"),
        ({"jwt_issuer": ""}, "jwt_issuer"),
        ({"jwt_leeway_seconds": 500}, "jwt_leeway_seconds"),
        ({"jwt_previous_keys": {"k1": TEST_SECRET}}, "must not contain the active"),
        ({"log_level": "LOUD"}, "log_level"),
    ],
)
def test_invalid_settings_fail_fast_without_leaking_values(overrides: dict, fragment: str) -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        _load(**overrides)
    message = str(excinfo.value)
    assert fragment in message
    for value in overrides.values():
        if isinstance(value, str) and len(value) > 8:
            assert value not in message
    assert TEST_SECRET not in message


def test_missing_required_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "JWT_SECRET_KEY", "JWT_ISSUER", "JWT_AUDIENCE"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(_env_file=None)
    for name in ("database_url", "jwt_secret_key", "jwt_issuer", "jwt_audience"):
        assert name in str(excinfo.value)
