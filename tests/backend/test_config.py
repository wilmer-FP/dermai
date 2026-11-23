import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_without_env_file():
    settings = Settings(_env_file=None)

    assert settings.app_name == "DermAI"
    assert settings.app_env == "development"
    assert settings.api_prefix == "/api/v1"


def test_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BACKEND_PORT", "9000")
    monkeypatch.setenv("DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.backend_port == 9000
    assert settings.debug is True


def test_cors_origins_are_split_and_trimmed():
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test ,")

    assert settings.cors_origins_list == ["http://a.test", "http://b.test"]


def test_invalid_environment_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="staging")
