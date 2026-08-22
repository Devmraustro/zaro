"""File storage with security defaults.

Phase 1.4 foundation for user-uploaded content. The design bakes in the
controls that are hard to retrofit:

- **Server-generated keys**: stored objects are keyed by ``category/uuid``;
  client filenames never touch the filesystem namespace.
- **Extension allow-list per category** plus **magic-byte verification**, so
  a ``.png`` upload that is really HTML/PHP cannot be stored or served back.
- **Hard size limits** enforced before any bytes hit disk.
- **Traversal-proof paths**: every key is resolved and required to stay
  inside the storage root.
- **HMAC-signed expiring URLs** so private objects can be served without
  making the storage tree publicly listable.

An S3 backend implements the same :class:`StorageBackend` protocol later;
call sites do not change.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError


class FileValidationError(BadRequestError):
    code = "invalid_file"


class FileKeyError(NotFoundError):
    code = "file_not_found"


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


class StorageBackend(Protocol):
    async def save(
        self, data: bytes, *, filename: str | None, content_type: str | None, category: str
    ) -> StoredFile: ...

    def open(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    """Filesystem backend rooted at ``settings.storage_local_dir``."""

    def __init__(self, settings: Settings, max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> None:
        self._root = Path(settings.storage_local_dir).resolve()
        self._max_bytes = max_upload_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    # -- save -----------------------------------------------------------------

    async def save(self, data: bytes, *, filename: str | None, content_type: str | None, category: str) -> StoredFile:
        if not data:
            raise FileValidationError("Empty files are not accepted")
        if len(data) > self._max_bytes:
            raise FileValidationError(f"File exceeds the {self._max_bytes} byte limit")

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

        key = f"{category}/{secrets.token_hex(16)}{extension}"
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

        return StoredFile(
            key=key,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            content_type=expected_type,
        )

    # -- read / delete ----------------------------------------------------------

    def open(self, key: str) -> bytes:
        path = self._resolve_key(key)
        if not path.is_file():
            raise FileKeyError("File does not exist")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve_key(key)
        if path.is_file():
            path.unlink()

    def _resolve_key(self, key: str) -> Path:
        if not key or ".." in key.replace("\\", "/").split("/"):
            raise FileKeyError("Invalid storage key")
        candidate = (self._root / key).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise FileKeyError("Invalid storage key")
        return candidate


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
    if settings.storage_backend == "local":
        return LocalFileStorage(settings)
    raise NotImplementedError("Only the local storage backend is implemented")
