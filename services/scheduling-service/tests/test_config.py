import pytest

from app.core.config import ConfigurationError, load_settings

BASE = {
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_issuer": "https://identity.unit-test.local",
    "jwt_audience": "smart-hospital-api",
    "facility_service_url": "http://facility.unit-test.local",
    "_env_file": None,
}
SECRET = "s" * 40


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"jwt_secret_key": "too-short-secret"}, "at least 32 bytes"),
        ({"jwt_secret_key": "REPLACE_WITH_RANDOM_SECRET_" + "a" * 20}, "placeholder"),
        ({"jwt_secret_key": SECRET, "jwt_algorithm": "none"}, "jwt_algorithm"),
        ({"jwt_secret_key": SECRET, "jwt_algorithm": "RS256"}, "jwt_algorithm"),
        ({"jwt_secret_key": SECRET, "jwt_algorithm": "HS512"}, "at least 64 bytes"),
        ({}, "jwt_secret_key"),
        ({"jwt_secret_key": SECRET, "facility_service_url": "ftp://facility"}, "facility_service_url"),
        ({"jwt_secret_key": SECRET, "facility_timeout_seconds": 0}, "facility_timeout_seconds"),
        ({"jwt_secret_key": SECRET, "extra_hours_slot_minutes": 4}, "extra_hours_slot_minutes"),
    ],
)
def test_invalid_configuration_fails_fast(overrides, expected) -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**{**BASE, **overrides})
    assert expected in str(excinfo.value)


def test_facility_service_url_is_required() -> None:
    values = {key: value for key, value in BASE.items() if key != "facility_service_url"}
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**values, jwt_secret_key=SECRET)
    assert "facility_service_url" in str(excinfo.value)


def test_configuration_errors_never_contain_secret_values() -> None:
    secret = "short-secret-value"
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**BASE, jwt_secret_key=secret)
    assert secret not in str(excinfo.value)


def test_previous_key_must_not_reuse_active_kid() -> None:
    with pytest.raises(ConfigurationError):
        load_settings(**BASE, jwt_secret_key=SECRET, jwt_key_id="k1", jwt_previous_keys={"k1": "p" * 40})


def test_valid_configuration() -> None:
    settings = load_settings(**BASE, jwt_secret_key=SECRET, jwt_algorithm="hs256")
    assert settings.jwt_algorithm == "HS256"
    assert settings.app_name == "scheduling-service"
    assert settings.extra_hours_slot_minutes == 15
    assert SECRET not in repr(settings)
