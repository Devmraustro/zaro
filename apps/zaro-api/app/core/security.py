import base64
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError, ValidationFailedError

TOKEN_TYPE_ACCESS = "access"

# Lazily-built static Argon2id hash of an unusable random value. Verified against
# when a login attempt references an unknown email so response timing matches
# the known-user path (mitigates user-enumeration via timing).
_dummy_hash: str | None = None

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def get_dummy_password_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _password_hasher.hash(secrets.token_urlsafe(24))
    return _dummy_hash


def validate_password_strength(password: str, min_length: int = 8) -> None:
    """Raise ValidationFailedError unless the password meets the policy.

    Policy: minimum length (default 8), maximum 128 characters, and at least
    one letter and one digit. Never reveals which rule failed beyond the
    minimum necessary to be actionable for the user.
    """
    if len(password) < min_length:
        raise ValidationFailedError(f"Password must be at least {min_length} characters long")
    if len(password) > 128:
        raise ValidationFailedError("Password must be at most 128 characters long")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValidationFailedError("Password must contain at least one letter and one digit")


def generate_refresh_secret() -> str:
    """Generate a high-entropy opaque refresh credential (never a JWT)."""
    return secrets.token_urlsafe(48)


def hash_refresh_secret(secret: str) -> str:
    """SHA-256 hex digest used as the server-side representation of a refresh credential."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_reset_token() -> str:
    """Generate a high-entropy single-use password reset token."""
    return secrets.token_urlsafe(48)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _encode(settings: Settings, payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _decode(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


def create_access_token(settings: Settings, subject: str, session_id: str | None = None) -> tuple[str, int]:
    """Create a short-lived access token.

    Claims are limited to identity and session attribution. No PII beyond the
    user id, no roles/permissions (authorization is server-side), no secrets.
    """
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = _utcnow()
    payload: dict[str, Any] = {
        "sub": subject,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_urlsafe(16),
    }
    if session_id is not None:
        payload["sid"] = session_id
    return _encode(settings, payload), int(expires_delta.total_seconds())


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    payload = _decode(settings, token)
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise UnauthorizedError("Invalid token type")
    return payload


def _fernet(settings: Settings) -> Fernet:
    key = settings.encryption_key
    if not key:
        derived = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
        key = derived.decode("utf-8")
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_secret(settings: Settings, value: str) -> str:
    return _fernet(settings).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(settings: Settings, value: str) -> str:
    return _fernet(settings).decrypt(value.encode("utf-8")).decode("utf-8")
