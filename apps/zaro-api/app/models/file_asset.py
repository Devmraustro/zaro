from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FilePurpose, FileVisibility, MediaKind
from app.models.mixins import UUIDPrimaryKeyMixin


class FileAsset(Base, UUIDPrimaryKeyMixin):
    """Generic stored-file record.

    One architecture for every upload purpose (custom-request inspiration,
    product media, future payment proofs). Access is always mediated:

    - private assets are served only through short-lived signed URLs after
      an ownership/permission check;
    - public assets (product media) may be served to anyone but are still
      addressed by server-generated keys, never client paths.
    """

    __tablename__ = "file_assets"

    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    purpose: Mapped[FilePurpose] = mapped_column(String(40), nullable=False, index=True)
    visibility: Mapped[FileVisibility] = mapped_column(String(20), nullable=False, default=FileVisibility.PRIVATE)

    # Ownership links (nullable; exactly the relevant ones are set per purpose)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    custom_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("custom_requests.id", ondelete="CASCADE"), nullable=True, index=True
    )
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Product-media editorial fields (only meaningful when purpose=product_media)
    media_kind: Mapped[MediaKind | None] = mapped_column(String(20), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
