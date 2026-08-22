import pytest
from pydantic import ValidationError

from app.core.config import Settings

_PRODUCTION_BASE = {
    "_env_file": None,
    "environment": "production",
    "secret_key": "p" * 48,
    "encryption_key": "e" * 48,
    "cors_origins": ["https://app.example.com"],
}


class TestProductionGate:
    def test_hardened_production_config_is_accepted(self):
        settings = Settings(**_PRODUCTION_BASE)
        assert settings.is_production is True
        assert settings.cookie_secure is True

    @pytest.mark.parametrize(
        "overrides",
        [
            {"debug": True},
            {"secret_key": "short"},
            {"secret_key": "change-me-in-production"},
            {"encryption_key": ""},
            {"cors_origins": ["*"]},
            {"cors_origins": []},
            {"cookie_secure_in_production_only": False},
            {"password_min_length": 4},
            {"access_token_expire_minutes": 120},
            {"allowed_hosts": ["*"]},
        ],
    )
    def test_insecure_production_configs_are_rejected(self, overrides: dict):
        merged = {**_PRODUCTION_BASE, **overrides}
        with pytest.raises(ValidationError) as excinfo:
            Settings(**merged)
        assert "Insecure production configuration" in str(excinfo.value) or any(
            marker in str(excinfo.value) for marker in ("secret_key", "Value error")
        )

    def test_staging_does_not_require_production_secrets(self):
        settings = Settings(_env_file=None, environment="staging")
        assert settings.is_staging_or_production is True
        # Staging still gets Secure cookies even without the full prod gate.
        assert settings.cookie_secure is True

    def test_development_keeps_plain_http_cookies(self):
        settings = Settings(_env_file=None)
        assert settings.cookie_secure is False

    def test_jwt_algorithm_locked_to_hs256(self):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, jwt_algorithm="none")  # type: ignore[arg-type]
