import os

import pytest

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError, ValidationFailedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    generate_refresh_secret,
    generate_reset_token,
    hash_password,
    hash_refresh_secret,
    hash_reset_token,
    validate_password_strength,
    verify_password,
)


@pytest.fixture(autouse=True)
def _clear_zaro_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("ZARO_"):
            monkeypatch.delenv(key, raising=False)


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        result = hash_password("test-password-123")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_is_not_plaintext(self):
        hashed = hash_password("my-secret-password")
        assert hashed != "my-secret-password"
        assert "my-secret-password" not in hashed

    def test_verify_correct_password(self):
        password = "correct-password-123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_produces_unique_hashes(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    def test_verify_empty_password_fails(self):
        hashed = hash_password("non-empty")
        assert verify_password("", hashed) is False

    def test_verify_malformed_hash_returns_false(self):
        assert verify_password("password", "not-a-valid-hash") is False


class TestJWT:
    def test_create_and_decode_access_token(self, settings):
        token, expires_in = create_access_token(settings, subject="user-123")
        assert isinstance(token, str)
        assert expires_in > 0
        payload = decode_access_token(settings, token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_access_token_rejects_garbage(self, settings):
        with pytest.raises(UnauthorizedError):
            decode_access_token(settings, "not.a.valid.token")

    def test_access_token_includes_session_when_provided(self, settings):
        token, _ = create_access_token(settings, subject="user-123", session_id="abc-123")
        payload = decode_access_token(settings, token)
        assert payload["sid"] == "abc-123"

    def test_access_token_omits_session_by_default(self, settings):
        token, _ = create_access_token(settings, subject="user-123")
        payload = decode_access_token(settings, token)
        assert "sid" not in payload


class TestOpaqueCredentials:
    def test_refresh_secrets_are_unique_and_long(self):
        a, b = generate_refresh_secret(), generate_refresh_secret()
        assert a != b
        assert len(a) >= 48

    def test_reset_tokens_are_unique_and_long(self):
        a, b = generate_reset_token(), generate_reset_token()
        assert a != b
        assert len(a) >= 48

    def test_hash_is_deterministic_and_irreversible(self):
        secret = generate_refresh_secret()
        assert hash_refresh_secret(secret) == hash_refresh_secret(secret)
        assert secret not in hash_refresh_secret(secret)
        assert len(hash_refresh_secret(secret)) == 64

    def test_reset_hash_matches_scheme(self):
        token = generate_reset_token()
        assert hash_reset_token(token) == hash_reset_token(token)
        assert len(hash_reset_token(token)) == 64


class TestPasswordPolicy:
    def test_valid_password_passes(self):
        validate_password_strength("goodpass1")

    def test_too_short_rejected(self):
        with pytest.raises(ValidationFailedError):
            validate_password_strength("ab1")

    def test_no_digit_rejected(self):
        with pytest.raises(ValidationFailedError):
            validate_password_strength("onlyletters")

    def test_no_letter_rejected(self):
        with pytest.raises(ValidationFailedError):
            validate_password_strength("12345678")

    def test_custom_min_length_respected(self):
        with pytest.raises(ValidationFailedError):
            validate_password_strength("ab1defg", min_length=10)

    def test_extremely_long_rejected(self):
        with pytest.raises(ValidationFailedError):
            validate_password_strength("a1" * 200)

    def test_decode_token_with_wrong_secret(self, settings):
        token, _ = create_access_token(settings, subject="user-123")
        wrong_settings = Settings.model_construct(
            secret_key="completely-different-secret-key",
            jwt_algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(UnauthorizedError):
            decode_access_token(wrong_settings, token)


class TestEncryption:
    def test_encrypt_and_decrypt(self, settings):
        original = "my-secret-api-key-12345"
        encrypted = encrypt_secret(settings, original)
        assert encrypted != original
        decrypted = decrypt_secret(settings, encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_output(self, settings):
        e1 = encrypt_secret(settings, "same-value")
        e2 = encrypt_secret(settings, "same-value")
        assert e1 != e2

    def test_decrypt_wrong_key_fails(self, settings):
        from cryptography.fernet import InvalidToken

        encrypted = encrypt_secret(settings, "secret-value")
        wrong_settings = Settings.model_construct(
            secret_key="wrong-key-for-encryption",
            encryption_key="",
        )
        with pytest.raises(InvalidToken):
            decrypt_secret(wrong_settings, encrypted)
