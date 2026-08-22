import time

import pytest

from app.core.config import Settings
from app.services.file_storage import (
    FileKeyError,
    FileValidationError,
    LocalFileStorage,
    normalize_filename,
    sign_url,
    sniff_content_type,
    verify_signed_url,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32


@pytest.fixture
def storage(tmp_path) -> LocalFileStorage:
    settings = Settings(_env_file=None, storage_local_dir=str(tmp_path / "storage"))
    return LocalFileStorage(settings)


class TestFilenameNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, ""),
            ("", ""),
            ("../../etc/passwd", "passwd"),
            ("..\\..\\windows\\evil.png", "evil.png"),
            ("my photo.png", "myphoto.png"),
            ("trailing dots...png...", "trailingdots...png"),
            ("\u202epng", "png"),
        ],
    )
    def test_normalization(self, raw, expected):
        assert normalize_filename(raw) == expected


class TestSniffContentType:
    def test_png(self):
        assert sniff_content_type(PNG_BYTES) == "image/png"

    def test_jpeg(self):
        assert sniff_content_type(JPEG_BYTES) == "image/jpeg"

    def test_unknown_returns_none(self):
        assert sniff_content_type(b"<html><body>not an image</body></html>") is None


class TestLocalFileStorageSave:
    async def test_valid_png_saved_with_server_generated_key(self, storage: LocalFileStorage):
        stored = await storage.save(PNG_BYTES, filename="avatar.png", content_type="image/png", category="avatars")
        assert stored.key.startswith("avatars/")
        assert stored.key.endswith(".png")
        assert "/" in stored.key
        # The client filename must not appear anywhere in the key.
        assert "avatar.png" not in stored.key
        assert stored.size == len(PNG_BYTES)

    async def test_extension_not_in_category_allowlist_rejected(self, storage: LocalFileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(PNG_BYTES, filename="avatar.gif", content_type="image/gif", category="avatars")

    async def test_content_mismatching_extension_rejected(self, storage: LocalFileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(JPEG_BYTES, filename="fake.png", content_type="image/png", category="avatars")

    async def test_unknown_content_rejected(self, storage: LocalFileStorage):
        html = b"<html></html>"
        with pytest.raises(FileValidationError):
            await storage.save(html, filename="page.png", content_type="image/png", category="avatars")

    async def test_empty_file_rejected(self, storage: LocalFileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(b"", filename="a.png", content_type="image/png", category="avatars")

    async def test_oversized_file_rejected(self, tmp_path):
        settings = Settings(_env_file=None, storage_local_dir=str(tmp_path / "s"))
        tiny_storage = LocalFileStorage(settings, max_upload_bytes=16)
        with pytest.raises(FileValidationError):
            await tiny_storage.save(PNG_BYTES, filename="big.png", content_type="image/png", category="avatars")

    async def test_unknown_category_rejected(self, storage: LocalFileStorage):
        with pytest.raises(FileValidationError):
            await storage.save(PNG_BYTES, filename="x.png", content_type="image/png", category="unknown")


class TestTraversalProtection:
    async def test_open_rejects_traversal_keys(self, storage: LocalFileStorage):
        for key in ("../secret.txt", "..\\secret.txt", "avatars/../../secret.txt", "", "/abs/path"):
            with pytest.raises(FileKeyError):
                storage.open(key)

    async def test_delete_rejects_traversal_keys(self, storage: LocalFileStorage):
        with pytest.raises(FileKeyError):
            storage.delete("../outside.txt")

    async def test_roundtrip_open_and_delete(self, storage: LocalFileStorage):
        stored = await storage.save(PNG_BYTES, filename="pic.png", content_type="image/png", category="avatars")
        assert storage.open(stored.key) == PNG_BYTES
        storage.delete(stored.key)
        with pytest.raises(FileKeyError):
            storage.open(stored.key)


class TestSignedUrls:
    def test_roundtrip(self, tmp_path):
        settings = Settings(_env_file=None, secret_key="k" * 48, storage_local_dir=str(tmp_path))
        token = sign_url(settings, "avatars/abc.png", expires_in_seconds=60)
        assert verify_signed_url(settings, "avatars/abc.png", token) is True

    def test_wrong_key_fails(self, tmp_path):
        settings = Settings(_env_file=None, secret_key="k" * 48, storage_local_dir=str(tmp_path))
        token = sign_url(settings, "avatars/abc.png")
        assert verify_signed_url(settings, "avatars/other.png", token) is False

    def test_tampered_expiry_fails(self, tmp_path):
        settings = Settings(_env_file=None, secret_key="k" * 48, storage_local_dir=str(tmp_path))
        token = sign_url(settings, "avatars/abc.png", expires_in_seconds=60)
        expires_raw, signature = token.split("|", 1)
        forged = f"{int(expires_raw) + 9999}|{signature}"
        assert verify_signed_url(settings, "avatars/abc.png", forged) is False

    def test_expired_token_fails(self, tmp_path):
        settings = Settings(_env_file=None, secret_key="k" * 48, storage_local_dir=str(tmp_path))
        expires_at = int(time.time()) - 10
        from app.services.file_storage import _url_signature

        token = f"{expires_at}|{_url_signature(settings, 'avatars/abc.png', expires_at)}"
        assert verify_signed_url(settings, "avatars/abc.png", token) is False

    def test_garbage_token_fails(self, tmp_path):
        settings = Settings(_env_file=None, secret_key="k" * 48, storage_local_dir=str(tmp_path))
        assert verify_signed_url(settings, "avatars/abc.png", "garbage") is False

    def test_ttl_is_capped(self, tmp_path):
        settings = Settings(_env_file=None, secret_key="k" * 48, storage_local_dir=str(tmp_path))
        with pytest.raises(ValueError):
            sign_url(settings, "avatars/abc.png", expires_in_seconds=100000)
