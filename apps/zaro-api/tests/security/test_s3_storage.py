"""S3 storage backend contract tests (in-memory fake, no real bucket/credentials).

Covers the same security contract as the local backend plus provider-error
sanitization and credential-leak protection.
"""

import io

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.services import file_storage
from app.services.file_storage import (
    FileKeyError,
    FileValidationError,
    S3FileStorage,
    StorageBackendError,
    get_storage_backend,
    sign_url,
    verify_signed_url,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32

_FAKE_ACCESS_KEY = "fake-access-key-value"
_FAKE_SECRET_KEY = "fake-secret-key-value"


class FakeS3Client:
    """Minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str | None = None) -> None:
        self.objects[Key] = Body

    def get_object(self, Bucket: str, Key: str) -> dict[str, object]:
        if Key not in self.objects:
            self._raise("NoSuchKey", "The specified key does not exist.")
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)

    @staticmethod
    def _raise(code: str, message: str) -> None:
        raise ClientError(
            {"Error": {"Code": code, "Message": message}, "ResponseMetadata": {"HTTPStatusCode": 400}},
            "operation",
        )


def make_settings(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "storage_backend": "s3",
        "s3_bucket": "fake-bucket",
        "s3_access_key": _FAKE_ACCESS_KEY,
        "s3_secret_key": _FAKE_SECRET_KEY,
        "s3_region": "us-east-1",
    }
    base.update(overrides)
    return Settings(**base)


def make_storage(fake: FakeS3Client, max_bytes: int = file_storage.DEFAULT_MAX_UPLOAD_BYTES) -> S3FileStorage:
    storage = S3FileStorage(make_settings(), max_upload_bytes=max_bytes)
    storage._client = fake
    return storage


@pytest.fixture
def fake() -> FakeS3Client:
    return FakeS3Client()


@pytest.fixture
def storage(fake: FakeS3Client) -> S3FileStorage:
    return make_storage(fake)


class TestBackendSelection:
    def test_default_backend_is_local(self):
        settings = Settings(_env_file=None)
        assert get_storage_backend(settings).__class__.__name__ == "LocalFileStorage"

    def test_s3_backend_is_selected(self):
        settings = make_settings()
        assert get_storage_backend(settings).__class__.__name__ == "S3FileStorage"


class TestS3Save:
    async def test_save_stores_object_and_returns_metadata(self, fake: FakeS3Client, storage: S3FileStorage):
        stored = await storage.save(PNG_BYTES, filename="avatar.png", content_type="image/png", category="avatars")
        assert fake.objects[stored.key] == PNG_BYTES
        assert stored.size == len(PNG_BYTES)
        assert stored.content_type == "image/png"

    async def test_generated_key_is_safe_and_server_generated(self, fake: FakeS3Client, storage: S3FileStorage):
        stored = await storage.save(PNG_BYTES, filename="avatar.png", content_type="image/png", category="avatars")
        assert stored.key.startswith("avatars/")
        assert stored.key.endswith(".png")
        assert "/" in stored.key
        assert ".." not in stored.key.replace("\\", "/").split("/")
        assert "avatar.png" not in stored.key

    async def test_extension_not_in_category_allowlist_rejected(self, storage: S3FileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(PNG_BYTES, filename="avatar.gif", content_type="image/gif", category="avatars")

    async def test_content_mismatching_extension_rejected(self, storage: S3FileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(JPEG_BYTES, filename="fake.png", content_type="image/png", category="avatars")

    async def test_unknown_content_rejected(self, storage: S3FileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(b"<html></html>", filename="page.png", content_type="image/png", category="avatars")

    async def test_empty_file_rejected(self, storage: S3FileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(b"", filename="a.png", content_type="image/png", category="avatars")

    async def test_oversized_file_rejected(self, fake: FakeS3Client):
        storage = make_storage(fake, max_bytes=16)
        with pytest.raises(FileValidationError):
            await storage.save(PNG_BYTES, filename="big.png", content_type="image/png", category="avatars")

    async def test_unknown_category_rejected(self, storage: S3FileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(PNG_BYTES, filename="x.png", content_type="image/png", category="unknown")


class TestS3TraversalProtection:
    async def test_open_rejects_traversal_keys(self, storage: S3FileStorage):
        for key in ("../secret.txt", "..\\secret.txt", "avatars/../../secret.txt", "", "/abs/path"):
            with pytest.raises(FileKeyError):
                await storage.open(key)

    async def test_delete_rejects_traversal_keys(self, storage: S3FileStorage):
        with pytest.raises(FileKeyError):
            await storage.delete("../outside.txt")


class TestS3ReadDelete:
    async def test_open_returns_saved_bytes(self, fake: FakeS3Client, storage: S3FileStorage):
        stored = await storage.save(PNG_BYTES, filename="pic.png", content_type="image/png", category="avatars")
        assert await storage.open(stored.key) == PNG_BYTES

    async def test_open_missing_key_raises_not_found(self, storage: S3FileStorage):
        with pytest.raises(FileKeyError):
            await storage.open("avatars/does-not-exist.png")

    async def test_delete_removes_object(self, fake: FakeS3Client, storage: S3FileStorage):
        stored = await storage.save(PNG_BYTES, filename="pic.png", content_type="image/png", category="avatars")
        await storage.delete(stored.key)
        assert stored.key not in fake.objects
        with pytest.raises(FileKeyError):
            await storage.open(stored.key)

    async def test_delete_missing_key_is_idempotent(self, storage: S3FileStorage):
        await storage.delete("avatars/never-existed.png")


class TestS3SignedUrls:
    def test_signed_url_roundtrip(self):
        settings = make_settings()
        token = sign_url(settings, "product_media/abc.png", expires_in_seconds=60)
        assert verify_signed_url(settings, "product_media/abc.png", token) is True

    def test_wrong_key_fails(self):
        settings = make_settings()
        token = sign_url(settings, "product_media/abc.png")
        assert verify_signed_url(settings, "product_media/other.png", token) is False

    def test_tampered_expiry_fails(self):
        settings = make_settings()
        token = sign_url(settings, "product_media/abc.png", expires_in_seconds=60)
        expires_raw, signature = token.split("|", 1)
        forged = f"{int(expires_raw) + 9999}|{signature}"
        assert verify_signed_url(settings, "product_media/abc.png", forged) is False

    def test_ttl_is_capped(self):
        settings = make_settings()
        with pytest.raises(ValueError):
            sign_url(settings, "product_media/abc.png", expires_in_seconds=100000)


class TestS3ErrorSanitization:
    async def test_provider_failure_is_sanitized(self, fake: FakeS3Client, storage: S3FileStorage, monkeypatch):
        def _boom(*args, **kwargs):
            fake._raise("InternalError", "internal provider malfunction")

        monkeypatch.setattr(fake, "get_object", _boom)
        with pytest.raises(StorageBackendError) as excinfo:
            await storage.open("product_media/x.png")
        assert str(excinfo.value) == "Storage backend error"

    async def test_save_provider_failure_is_sanitized(self, fake: FakeS3Client, storage: S3FileStorage, monkeypatch):
        def _boom(*args, **kwargs):
            fake._raise("ServiceUnavailable", "temporary outage")

        monkeypatch.setattr(fake, "put_object", _boom)
        with pytest.raises(StorageBackendError):
            await storage.save(PNG_BYTES, filename="pic.png", content_type="image/png", category="avatars")

    async def test_credentials_and_raw_messages_never_leak(
        self, fake: FakeS3Client, storage: S3FileStorage, monkeypatch
    ):
        leaks = [f"AccessDenied for key {_FAKE_ACCESS_KEY}", _FAKE_SECRET_KEY, "NoSuchBucket: fake-bucket"]
        captured: list[tuple[str, str]] = []

        def record_error(event: str, **kw):
            captured.append((event, str(kw)))

        monkeypatch.setattr(file_storage.logger, "error", record_error)

        def _boom(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {"Code": "AccessDenied", "Message": " ".join(leaks)},
                    "ResponseMetadata": {"HTTPStatusCode": 403},
                },
                "GetObject",
            )

        monkeypatch.setattr(fake, "get_object", _boom)
        with pytest.raises(StorageBackendError) as excinfo:
            await storage.open("product_media/x.png")

        for leak in leaks:
            assert leak not in str(excinfo.value)
        assert str(excinfo.value) == "Storage backend error"
        assert captured, "expected a sanitized error log"
        for _, payload in captured:
            assert all(leak not in payload for leak in leaks)
