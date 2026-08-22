"""Server-side authentication session tracking.

Sessions are the authoritative server-side record behind refresh credentials.
Raw refresh tokens are never stored — only their SHA-256 hash.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin

# Reasons a session can be revoked with.
REVOKE_REASON_LOGOUT = "logout"
REVOKE_REASON_ROTATED = "rotated"
REVOKE_REASON_PASSWORD_CHANGE = "password_change"
REVOKE_REASON_PASSWORD_RESET = "password_reset"
REVOKE_REASON_REUSE_DETECTED = "reuse_detected"
REVOKE_REASON_EXPIRED = "expired"
REVOKE_REASON_ADMIN = "admin"
REVOKE_REASON_ACCOUNT_DISABLED = "account_disabled"
REVOKE_REASON_SESSION_LIMIT = "session_limit"


class AuthSession(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # All rotations of one login share a family id; reuse detection revokes families.
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    # SHA-256 hex digest of the opaque refresh secret. Raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def __repr__(self) -> str:
        return f"<AuthSession id={self.id} user_id={self.user_id} revoked={self.revoked_at is not None}>"
