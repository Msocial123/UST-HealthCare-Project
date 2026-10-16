import pytest

from app.core.config import ConfigurationError, load_settings

BASE = {
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_issuer": "https://identity.unit-test.local",
    "jwt_audience": "smart-hospital-api",
    "_env_file": None,
}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"jwt_secret_key": "too-short-secret"}, "at least 32 bytes"),
        ({"jwt_secret_key": "REPLACE_WITH_RANDOM_SECRET_" + "a" * 20}, "placeholder"),
        ({"jwt_secret_key": "s" * 40, "jwt_algorithm": "none"}, "jwt_algorithm"),
        ({"jwt_secret_key": "s" * 40, "jwt_algorithm": "RS256"}, "jwt_algorithm"),
        ({"jwt_secret_key": "s" * 40, "jwt_algorithm": "HS512"}, "at least 64 bytes"),
        ({}, "jwt_secret_key"),
    ],
)
def test_invalid_configuration_fails_fast(overrides, expected) -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**BASE, **overrides)
    assert expected in str(excinfo.value)


def test_configuration_errors_never_contain_secret_values() -> None:
    secret = "short-secret-value"
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**BASE, jwt_secret_key=secret)
    assert secret not in str(excinfo.value)


def test_previous_key_must_not_reuse_active_kid() -> None:
    with pytest.raises(ConfigurationError):
        load_settings(**BASE, jwt_secret_key="s" * 40, jwt_key_id="k1", jwt_previous_keys={"k1": "p" * 40})


def test_valid_configuration() -> None:
    settings = load_settings(**BASE, jwt_secret_key="s" * 40, jwt_algorithm="hs256")
    assert settings.jwt_algorithm == "HS256"
    assert settings.app_name == "provider-service"
    assert "s" * 40 not in repr(settings)
