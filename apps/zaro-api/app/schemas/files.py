"""File asset schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FileAssetResponse(BaseModel):
    id: UUID
    original_filename: str | None
    content_type: str
    size_bytes: int
    purpose: str
    visibility: str
    media_kind: str | None
    alt_text: str | None
    sort_order: int
    created_at: datetime


class FileAccessUrlResponse(BaseModel):
    """Short-lived signed URL for a private asset."""

    url_path: str
    expires_in: int


class ProductMediaUploadMeta(BaseModel):
    """Form metadata accompanying a product media upload."""

    media_kind: str = Field(default="gallery", pattern=r"^(hero|gallery|detail|lifestyle|video)$")
    alt_text: str | None = Field(default=None, max_length=300)
    sort_order: int = Field(default=0, ge=0, le=10000)
