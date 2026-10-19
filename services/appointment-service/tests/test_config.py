from pathlib import Path

import pytest

from app.core.config import ConfigurationError, load_settings

BASE = {
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_issuer": "https://identity.unit-test.local",
    "jwt_audience": "smart-hospital-api",
    "_env_file": None,
}
SECRET = "s" * 40
ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"jwt_secret_key": "too-short-secret"}, "at least 32 bytes"),
        ({"jwt_secret_key": "REPLACE_WITH_RANDOM_SECRET_" + "a" * 20}, "placeholder"),
        ({"jwt_secret_key": SECRET, "jwt_algorithm": "none"}, "jwt_algorithm"),
        ({"jwt_secret_key": SECRET, "jwt_algorithm": "RS256"}, "jwt_algorithm"),
        ({"jwt_secret_key": SECRET, "jwt_algorithm": "HS512"}, "at least 64 bytes"),
        ({}, "jwt_secret_key"),
        ({"jwt_secret_key": SECRET, "scheduling_advice_enabled": True}, "SCHEDULING_SERVICE_URL is required"),
        ({"jwt_secret_key": SECRET, "scheduling_service_url": "ftp://scheduling"}, "scheduling_service_url"),
        ({"jwt_secret_key": SECRET, "scheduling_timeout_seconds": 0}, "scheduling_timeout_seconds"),
        ({"jwt_secret_key": SECRET, "appointments_enabled": "maybe"}, "appointments_enabled"),
    ],
)
def test_invalid_configuration_fails_fast(overrides, expected) -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**{**BASE, **overrides})
    assert expected in str(excinfo.value)


def test_configuration_errors_never_contain_secret_values() -> None:
    secret = "short-secret-value"
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(**BASE, jwt_secret_key=secret)
    assert secret not in str(excinfo.value)


def test_previous_key_must_not_reuse_active_kid() -> None:
    with pytest.raises(ConfigurationError):
        load_settings(**BASE, jwt_secret_key=SECRET, jwt_key_id="k1", jwt_previous_keys={"k1": "p" * 40})


def test_valid_configuration_defaults() -> None:
    settings = load_settings(**BASE, jwt_secret_key=SECRET, jwt_algorithm="hs256")
    assert settings.jwt_algorithm == "HS256"
    assert settings.app_name == "appointment-service"
    assert settings.appointments_enabled is False  # patient-facing booking is OFF unless enabled
    assert settings.scheduling_advice_enabled is False
    assert SECRET not in repr(settings)


def test_env_example_has_flag_off_and_placeholders_only() -> None:
    lines = [line.split("#")[0].strip() for line in ENV_EXAMPLE.read_text().splitlines()]
    values = dict(line.split("=", 1) for line in lines if "=" in line)
    assert values["APPOINTMENTS_ENABLED"] == "false"
    assert values["SCHEDULING_ADVICE_ENABLED"] == "false"
    assert "REPLACE_WITH" in values["JWT_SECRET_KEY"]
    assert "REPLACE_WITH" in values["DATABASE_URL"]
