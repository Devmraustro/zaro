import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "staging", "production"]
StorageBackendName = Literal["local", "s3"]

_DEV_SECRET_VALUES = frozenset({"change-me-in-production", "dev-zaro-secret-key-change-in-production"})


class Settings(BaseSettings):
    """Application configuration sourced from environment variables prefixed with ``ZARO_``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ZARO_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "ZARO API"
    environment: AppEnvironment = "development"
    debug: bool = False
    version: str = "0.1.0"

    api_v1_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    openapi_url: str = "/openapi.json"

    # --- Security ----------------------------------------------------------
    secret_key: str = "change-me-in-production"
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    encryption_key: str = ""
    password_min_length: int = 8

    # --- Authentication sessions / cookies ---------------------------------
    refresh_cookie_name: str = "zaro_refresh"
    csrf_cookie_name: str = "zaro_csrf"
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_secure_in_production_only: bool = True
    max_sessions_per_user: int = 20

    # --- Password reset ----------------------------------------------------
    password_reset_token_expire_minutes: int = 30

    # --- Network trust -----------------------------------------------------
    # Explicit list of proxy IPs/networks allowed to set X-Forwarded-For.
    # Empty means the header is never trusted (direct client IP is used).
    trusted_proxies: list[str] = Field(default_factory=list)
    # When non-empty, requests whose Host header is not in this list are
    # rejected with 421. Empty disables host validation (development only).
    allowed_hosts: list[str] = Field(default_factory=list)

    # --- Infrastructure ----------------------------------------------------
    database_url: str = "postgresql+asyncpg://zaro:zaro@localhost:5432/zaro"
    redis_url: str = "redis://localhost:6379/1"

    # --- HTTP --------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3001"])
    # Reject request bodies larger than this before parsing (bytes).
    max_request_bytes: int = 1024 * 1024

    # --- File Storage ------------------------------------------------------
    storage_backend: StorageBackendName = "local"
    storage_local_dir: str = "./storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "zaro-assets"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    # --- Rate Limiting -----------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # Authentication-specific limits (fixed windows).
    login_ip_limit: int = 10
    login_email_limit: int = 5
    auth_window_seconds: int = 60
    # Credential-stuffing guard: failures per email over a longer window.
    login_failure_email_limit: int = 10
    login_failure_window_seconds: int = 900
    password_reset_request_limit: int = 5
    password_reset_confirm_limit: int = 10
    reset_window_seconds: int = 3600

    # --- Pagination --------------------------------------------------------
    default_page_size: int = 20
    max_page_size: int = 100

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(origin) for origin in parsed]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _parse_allowed_hosts(cls, value: object) -> object:
        return Settings._parse_cors_origins(value)

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: str, info) -> str:
        env = info.data.get("environment", "development")
        if env == "production" and value in _DEV_SECRET_VALUES:
            raise ValueError("secret_key must be changed in production")
        return value

    @model_validator(mode="after")
    def _validate_production_posture(self) -> "Settings":
        """Fail fast when production would inherit unsafe defaults.

        Every rule here corresponds to a finding in the Phase 1.4 security
        review; see docs/ZARO_PHASE_1_4_SECURITY_REVIEW.md (H1, M2, M4, M5).
        """
        if self.environment != "production":
            return self

        errors: list[str] = []
        if self.debug:
            errors.append("debug must be false in production")
        if len(self.secret_key) < 32 or self.secret_key in _DEV_SECRET_VALUES:
            errors.append("secret_key must be at least 32 random characters in production")
        if not self.encryption_key:
            errors.append("encryption_key must be set explicitly in production")
        wildcard_cors = any(origin.strip() == "*" for origin in self.cors_origins)
        if not self.cors_origins or wildcard_cors:
            errors.append("cors_origins must be an explicit origin list in production")
        if not self.cookie_secure_in_production_only:
            errors.append("cookie_secure_in_production_only cannot disable Secure cookies in production")
        if self.cookie_samesite == "none" and not self.cookie_secure_in_production_only:
            errors.append("SameSite=None requires Secure cookies")
        if self.password_min_length < 8:
            errors.append("password_min_length must be at least 8 in production")
        if self.access_token_expire_minutes > 60:
            errors.append("access_token_expire_minutes must not exceed 60 in production")
        if "*" in self.allowed_hosts:
            errors.append("allowed_hosts must not contain wildcards in production")
        if errors:
            raise ValueError("Insecure production configuration: " + "; ".join(errors))
        return self

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_staging_or_production(self) -> bool:
        return self.environment in ("staging", "production")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies are mandatory in staging/production.

        ``cookie_secure_in_production_only`` exists so local plain-HTTP
        development can receive cookies at all; disabling it in staging or
        production is rejected by the production posture validator.
        """
        if self.cookie_secure_in_production_only:
            return self.is_staging_or_production
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
