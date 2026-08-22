import os

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def _clear_zaro_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("ZARO_"):
            monkeypatch.delenv(key, raising=False)


class TestSettings:
    def test_default_settings(self):
        settings = Settings(_env_file=None)
        assert settings.app_name == "ZARO API"
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.api_v1_prefix == "/api/v1"
        assert settings.jwt_algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30
        assert settings.refresh_token_expire_days == 30
        assert settings.default_page_size == 20
        assert settings.max_page_size == 100

    def test_cors_origins_from_json_array(self):
        settings = Settings(_env_file=None, cors_origins=["http://a.com", "http://b.com"])
        assert settings.cors_origins == ["http://a.com", "http://b.com"]

    def test_cors_origins_from_csv(self):
        settings = Settings(_env_file=None, cors_origins="http://a.com, http://b.com")
        assert settings.cors_origins == ["http://a.com", "http://b.com"]

    def test_cors_origins_from_list(self):
        settings = Settings(_env_file=None, cors_origins=["http://c.com"])
        assert settings.cors_origins == ["http://c.com"]

    def test_is_test_property(self):
        settings = Settings(_env_file=None, environment="test")
        assert settings.is_test is True
        assert settings.is_production is False

    def test_is_production_property(self):
        settings = Settings(
            _env_file=None,
            environment="production",
            secret_key="a-production-safe-secret-key-min-32-chars",
            encryption_key="a-production-encryption-key-min-32-chars",
        )
        assert settings.is_production is True
        assert settings.is_test is False

    def test_secret_key_not_empty_in_production(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Settings(_env_file=None, environment="production", secret_key="change-me-in-production")
