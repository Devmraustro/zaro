"""File storage with security defaults.

Phase 1.4 foundation for user-uploaded content. The design bakes in the
controls that are hard to retrofit:

- **Server-generated keys**: stored objects are keyed by ``category/uuid``;
  client filenames never touch the storage namespace.
- **Extension allow-list per category** plus **magic-byte verification**, so
  a ``.png`` upload that is really HTML/PHP cannot be stored or served back.
- **Hard size limits** enforced before any bytes reach storage.
- **Traversal-proof keys**: every key is validated and required to stay
  inside its intended namespace (path resolution for the local backend,
  sanitized key checks for S3).
- **HMAC-signed expiring URLs** so private objects can be served without
  making the storage tree publicly listable.

Both the local and the S3 backend implement the same async
:class:`StorageBackend` protocol; call sites do not change.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.exceptions import AppError, BadRequestError, NotFoundError
from app.core.logging import get_logger

logger = get_logger("app.services.file_storage")


class FileValidationError(BadRequestError):
    code = "invalid_file"


class FileKeyError(NotFoundError):
    code = "file_not_found"


class StorageBackendError(AppError):
    status_code = 500
    code = "storage_error"


# --- Content-type policy -----------------------------------------------------

_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # RIFF container; WEBP marker checked separately
    "application/pdf": (b"%PDF-",),
}

_EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

_CATEGORY_EXTENSIONS: dict[str, frozenset[str]] = {
    "avatars": frozenset({".png", ".jpg", ".jpeg", ".webp"}),
    "documents": frozenset({".pdf"}),
    # Phase 2: custom-request inspiration shots (images + PDF sketches)
    "inspiration": frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}),
    # Phase 2: public product media
    "product_media": frozenset({".png", ".jpg", ".jpeg", ".webp"}),
    # Phase 3: manual CCP payment proofs (images + PDF receipts)
    "payment_proofs": frozenset({".png", ".jpg", ".jpeg", ".webp", ".pdf"}),
}

DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    key: str
    size: int
    sha256: str
    content_type: str


def normalize_filename(filename: str | None) -> str:
    """Strip directory components and control characters from a client filename."""
    if not filename:
        return ""
    name = unicodedata.normalize("NFKC", filename)
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in name if (ch.isprintable() and not ch.isspace()) or ch == ".").strip(". ")
    return cleaned[:255]


def sniff_content_type(data: bytes) -> str | None:
    """Return the declared-by-bytes content type, or None when unrecognized."""
    for content_type, signatures in _MAGIC_SIGNATURES.items():
        if any(data.startswith(sig) for sig in signatures):
            if content_type == "image/webp":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return content_type
                continue
            return content_type
    return None


def _validate_storage_key(key: str) -> None:
    if not key or ".." in key.replace("\\", "/").split("/"):
        raise FileKeyError("Invalid storage key")


def _validate_upload(
    data: bytes, *, filename: str | None, category: str, max_bytes: int
) -> tuple[str, str]:
    """Validate a candidate upload and return ``(extension, content_type)``.

    Shared by every storage backend so validation cannot drift between backends.
    """
    if not data:
        raise FileValidationError("Empty files are not accepted")
    if len(data) > max_bytes:
        raise FileValidationError(f"File exceeds the {max_bytes} byte limit")

    allowed_extensions = _CATEGORY_EXTENSIONS.get(category)
    if allowed_extensions is None:
        raise FileValidationError(f"Unknown storage category '{category}'")

    clean_name = normalize_filename(filename)
    extension = Path(clean_name).suffix.lower() if clean_name else ""
    if not extension or extension not in allowed_extensions:
        raise FileValidationError(f"Files of type '{extension or 'unknown'}' are not allowed here")

    expected_type = _EXTENSION_TO_CONTENT_TYPE[extension]
    detected_type = sniff_content_type(data)
    if detected_type != expected_type:
        raise FileValidationError("File contents do not match its extension")

    return extension, expected_type


def _new_storage_key(category: str, extension: str) -> str:
    return f"{category}/{secrets.token_hex(16)}{extension}"


class StorageBackend(Protocol):
    async def save(
        self, data: bytes, *, filename: str | None, content_type: str | None, category: str
    ) -> StoredFile: ...

    async def open(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalFileStorage:
    """Filesystem backend rooted at ``settings.storage_local_dir``."""

    def __init__(self, settings: Settings, max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> None:
        self._root = Path(settings.storage_local_dir).resolve()
        self._max_bytes = max_upload_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    # -- save -----------------------------------------------------------------

    async def save(self, data: bytes, *, filename: str | None, content_type: str | None, category: str) -> StoredFile:
        extension, expected_type = _validate_upload(
            data, filename=filename, category=category, max_bytes=self._max_bytes
        )
        key = _new_storage_key(category, extension)
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

        return StoredFile(
            key=key,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            content_type=expected_type,
        )

    # -- read / delete ----------------------------------------------------------

    async def open(self, key: str) -> bytes:
        path = self._resolve_key(key)
        if not path.is_file():
            raise FileKeyError("File does not exist")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve_key(key)
        if path.is_file():
            await asyncio.to_thread(path.unlink)

    def _resolve_key(self, key: str) -> Path:
        _validate_storage_key(key)
        candidate = (self._root / key).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise FileKeyError("Invalid storage key")
        return candidate


class S3FileStorage:
    """S3-compatible object storage backend.

    Objects are stored privately (no public ACL) and are never exposed
    directly: read access flows through the app-level HMAC-signed URL proxy
    (``/api/v1/files/<id>/content?token=<token>``), so the bucket is not
    publicly listable and keys get the same validation as the local backend.

    Network calls run in worker threads so the event loop is never blocked.
    Provider errors are turned into a sanitized :class:`StorageBackendError`;
    credentials and raw SDK messages are never returned or logged.
    """

    def __init__(self, settings: Settings, max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> None:
        self._settings = settings
        self._max_bytes = max_upload_bytes
        self._client: Any | None = None

    async def save(self, data: bytes, *, filename: str | None, content_type: str | None, category: str) -> StoredFile:
        extension, expected_type = _validate_upload(
            data, filename=filename, category=category, max_bytes=self._max_bytes
        )
        key = _new_storage_key(category, extension)
        client = self._get_client()
        try:
            await asyncio.to_thread(
                client.put_object,
                Bucket=self._settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=expected_type,
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._sanitized_error("save", exc) from exc

        return StoredFile(
            key=key,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            content_type=expected_type,
        )

    async def open(self, key: str) -> bytes:
        _validate_storage_key(key)
        client = self._get_client()
        try:
            obj = await asyncio.to_thread(client.get_object, Bucket=self._settings.s3_bucket, Key=key)
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if code in {"NoSuchKey", "NotFound", "404"}:
                raise FileKeyError("File does not exist") from exc
            raise self._sanitized_error("open", exc) from exc
        except BotoCoreError as exc:
            raise self._sanitized_error("open", exc) from exc
        try:
            return await asyncio.to_thread(obj["Body"].read)
        except (ClientError, BotoCoreError) as exc:
            raise self._sanitized_error("open", exc) from exc

    async def delete(self, key: str) -> None:
        _validate_storage_key(key)
        client = self._get_client()
        try:
            await asyncio.to_thread(client.delete_object, Bucket=self._settings.s3_bucket, Key=key)
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if code in {"NoSuchKey", "NotFound", "404"}:
                return
            raise self._sanitized_error("delete", exc) from exc
        except BotoCoreError as exc:
            raise self._sanitized_error("delete", exc) from exc

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            session = boto3.Session(
                aws_access_key_id=self._settings.s3_access_key,
                aws_secret_access_key=self._settings.s3_secret_key,
                region_name=self._settings.s3_region,
            )
            endpoint: dict[str, str] = {}
            if self._settings.s3_endpoint_url:
                endpoint["endpoint_url"] = self._settings.s3_endpoint_url
            self._client = session.client("s3", **endpoint)
        return self._client

    @staticmethod
    def _sanitized_error(operation: str, exc: Exception) -> StorageBackendError:
        code = exc.response.get("Error", {}).get("Code") if isinstance(exc, ClientError) else type(exc).__name__
        logger.error(
            "storage_backend_error",
            operation=operation,
            error=type(exc).__name__,
            error_code=code,
        )
        return StorageBackendError("Storage backend error")


# --- Signed URLs ---------------------------------------------------------------

_SIGNED_URL_TTL_MAX_SECONDS = 3600


def sign_url(settings: Settings, key: str, expires_in_seconds: int = 300) -> str:
    """Produce ``exp|signature`` suffix proving read access to ``key`` until expiry."""
    if expires_in_seconds <= 0 or expires_in_seconds > _SIGNED_URL_TTL_MAX_SECONDS:
        raise ValueError(f"expires_in_seconds must be between 1 and {_SIGNED_URL_TTL_MAX_SECONDS}")
    expires_at = int(time.time()) + expires_in_seconds
    signature = _url_signature(settings, key, expires_at)
    return f"{expires_at}|{signature}"


def verify_signed_url(settings: Settings, key: str, token: str) -> bool:
    try:
        expires_raw, signature = token.split("|", 1)
        expires_at = int(expires_raw)
    except ValueError:
        return False
    if expires_at < int(time.time()):
        return False
    expected = _url_signature(settings, key, expires_at)
    return hmac.compare_digest(expected, signature)


def _url_signature(settings: Settings, key: str, expires_at: int) -> str:
    message = f"{key}:{expires_at}".encode()
    return hmac.new(settings.secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def get_storage_backend(settings: Settings) -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3FileStorage(settings)
    return LocalFileStorage(settings)
