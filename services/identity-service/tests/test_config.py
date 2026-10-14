import pytest

from app.core.config import ConfigurationError, load_settings
from tests.conftest import TEST_SECRET, make_settings

BASE = {
    "_env_file": None,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_issuer": "https://identity.unit-test.local",
    "jwt_audience": "smart-hospital-api",
}


def test_valid_settings_load() -> None:
    settings = make_settings()
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_token_expire_minutes == 15
    assert settings.verification_keys == {"test-k1": TEST_SECRET.encode()}


def test_secret_is_masked_in_repr() -> None:
    assert TEST_SECRET not in repr(make_settings())


def test_missing_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="jwt_secret_key"):
        load_settings(**BASE)


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"jwt_secret_key": "too-short-secret"}, "at least 32 bytes"),
        ({"jwt_secret_key": "REPLACE_WITH_RANDOM_SECRET_VALUE_0123456789"}, "placeholder"),
        ({"jwt_secret_key": "change-me-" + "a" * 40}, "placeholder"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_algorithm": "none"}, "jwt_algorithm"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_algorithm": "RS256"}, "jwt_algorithm"),
        ({"jwt_secret_key": "a1b2" * 12, "jwt_algorithm": "HS512"}, "at least 64 bytes"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_access_token_expire_minutes": 61}, "expire"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_access_token_expire_minutes": 0}, "expire"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_issuer": ""}, "jwt_issuer"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_previous_keys": {"old": "short"}}, "'old'"),
        ({"jwt_secret_key": TEST_SECRET, "jwt_previous_keys": {"k1": TEST_SECRET + "x"}}, "active"),
        ({"jwt_secret_key": TEST_SECRET, "log_level": "VERBOSE"}, "log_level"),
    ],
)
def test_invalid_settings_are_rejected(overrides: dict, fragment: str) -> None:
    with pytest.raises(ConfigurationError, match=fragment):
        load_settings(**{**BASE, **overrides})


def test_configuration_errors_never_include_secret_values() -> None:
    weak_secret = "weak-but-identifiable-value"
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(**BASE, jwt_secret_key=weak_secret)
    assert weak_secret not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
