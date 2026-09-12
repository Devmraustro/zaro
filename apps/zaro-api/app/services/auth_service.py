"""Authentication and session lifecycle service.

Security invariants enforced here:

- Raw refresh credentials and reset tokens are never persisted; only SHA-256 hashes.
- Refresh rotation revokes the used credential and issues a new one in the same family.
- Reuse of a rotated credential is treated as potential token theft: the whole
  session family is revoked and a security audit event is recorded.
- Login failures are indistinguishable between unknown email / wrong password /
  disabled account (generic error, timing-equalized).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import (
    generate_refresh_secret,
    generate_reset_token,
    get_dummy_password_hash,
    hash_password,
    hash_refresh_secret,
    hash_reset_token,
    validate_password_strength,
    verify_password,
)
from app.models.auth_session import (
    REVOKE_REASON_ACCOUNT_DISABLED,
    REVOKE_REASON_EXPIRED,
    REVOKE_REASON_PASSWORD_CHANGE,
    REVOKE_REASON_PASSWORD_RESET,
    REVOKE_REASON_REUSE_DETECTED,
    REVOKE_REASON_ROTATED,
    REVOKE_REASON_SESSION_LIMIT,
    AuthSession,
)
from app.models.password_reset import PasswordResetToken
from app.models.user import User

logger = get_logger("app.services.auth")

GENERIC_INVALID_CREDENTIALS = "Invalid email or password"
GENERIC_INVALID_REFRESH = "Invalid or expired refresh token"


class LoginFailure(Exception):
    """Internal signal; endpoints translate this into a generic 401 response."""

    def __init__(self, reason: str) -> None:
        super().__init__("authentication failed")
        self.reason = reason


class InvalidRefreshToken(Exception):
    def __init__(self, reason: str = "invalid") -> None:
        super().__init__("invalid refresh token")
        self.reason = reason


class RefreshReuseDetected(InvalidRefreshToken):
    def __init__(self, user_id: uuid.UUID | None = None) -> None:
        super().__init__("reuse_detected")
        self.user_id = user_id


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime) -> datetime:
    """Normalize DB datetimes to UTC-aware (SQLite returns naive values)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _rowcount(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Public wrapper for lookups that need the user after a service call."""
    return await _get_user_by_email(db, email)


async def revoke_session_by_secret(db: AsyncSession, *, user_id: uuid.UUID, refresh_secret: str, reason: str) -> bool:
    """Revoke the session matching a raw refresh credential, enforcing ownership."""
    token_hash = hash_refresh_secret(refresh_secret)
    result = await db.execute(select(AuthSession).where(AuthSession.token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is None or session.user_id != user_id:
        return False
    if session.revoked_at is not None:
        return True
    session.revoked_at = _utcnow()
    session.revoke_reason = reason
    await db.flush()
    return True


async def is_refresh_session_live(db: AsyncSession, *, refresh_secret: str) -> bool:
    """True when a raw refresh credential maps to a live browser session.

    Pure read: no rotation, no revocation, no reuse signal -- so the session
    bootstrap endpoint can probe the HttpOnly cookie on a cold page load
    without churning the refresh credential or minting tokens.
    """
    token_hash = hash_refresh_secret(refresh_secret)
    result = await db.execute(select(AuthSession).where(AuthSession.token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return False
    if _as_utc(session.expires_at) <= _utcnow():
        return False
    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user = user_result.scalar_one_or_none()
    return user is not None and user.is_active


async def authenticate_login(
    db: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, AuthSession, str]:
    """Validate credentials and create a new session.

    Returns (user, session, raw_refresh_secret). Raises LoginFailure with an
    internal reason on any failure — callers must respond generically.
    """
    user = await _get_user_by_email(db, email)
    if user is None:
        # Equalize timing with the known-user path before failing.
        verify_password(password, get_dummy_password_hash())
        raise LoginFailure("unknown_email")

    if not verify_password(password, user.hashed_password):
        raise LoginFailure("invalid_password")

    if not user.is_active:
        raise LoginFailure("account_disabled")

    session, refresh_secret = await create_session_for_user(
        db, settings, user=user, ip_address=ip_address, user_agent=user_agent
    )
    user.last_login_at = _utcnow()
    return user, session, refresh_secret


async def create_session_for_user(
    db: AsyncSession,
    settings: Settings,
    *,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[AuthSession, str]:
    await _prune_session_limit(db, settings, user)

    refresh_secret = generate_refresh_secret()
    now = _utcnow()
    session = AuthSession(
        user_id=user.id,
        family_id=uuid.uuid4(),
        token_hash=hash_refresh_secret(refresh_secret),
        created_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        last_used_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(session)
    await db.flush()
    return session, refresh_secret


async def _prune_session_limit(db: AsyncSession, settings: Settings, user: User) -> None:
    """Keep the number of active sessions per user within the configured maximum."""
    limit = max(1, settings.max_sessions_per_user)
    result = await db.execute(
        select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .order_by(AuthSession.created_at.asc())
    )
    active = list(result.scalars().all())
    excess = len(active) - (limit - 1)  # reserve one slot for the upcoming session
    if excess <= 0:
        return
    for stale in active[:excess]:
        stale.revoked_at = _utcnow()
        stale.revoke_reason = REVOKE_REASON_SESSION_LIMIT


async def rotate_refresh_token(
    db: AsyncSession,
    settings: Settings,
    *,
    refresh_secret: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, AuthSession, str]:
    """Rotate a refresh credential. Detects reuse of rotated credentials."""
    token_hash = hash_refresh_secret(refresh_secret)
    result = await db.execute(select(AuthSession).where(AuthSession.token_hash == token_hash))
    session = result.scalar_one_or_none()

    if session is None:
        raise InvalidRefreshToken("not_found")

    if session.revoked_at is not None:
        if session.revoke_reason == REVOKE_REASON_ROTATED:
            # Previously rotated credential presented again -> possible theft.
            await revoke_session_family(db, session.family_id, REVOKE_REASON_REUSE_DETECTED)
            raise RefreshReuseDetected(session.user_id)
        raise InvalidRefreshToken(f"revoked:{session.revoke_reason}")

    now = _utcnow()
    if _as_utc(session.expires_at) <= now:
        session.revoked_at = now
        session.revoke_reason = REVOKE_REASON_EXPIRED
        raise InvalidRefreshToken("expired")

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        await revoke_session_family(db, session.family_id, REVOKE_REASON_ACCOUNT_DISABLED)
        raise InvalidRefreshToken("account_disabled")

    # Rotate: retire the presented credential, issue a sibling in the same family.
    session.revoked_at = now
    session.revoke_reason = REVOKE_REASON_ROTATED

    new_secret = generate_refresh_secret()
    new_session = AuthSession(
        user_id=session.user_id,
        family_id=session.family_id,
        token_hash=hash_refresh_secret(new_secret),
        created_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        last_used_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or session.user_agent or "")[:500] or None,
    )
    db.add(new_session)
    await db.flush()
    return user, new_session, new_secret


async def revoke_session_family(db: AsyncSession, family_id: uuid.UUID, reason: str) -> int:
    now = _utcnow()
    result = await db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason)
    )
    await db.flush()
    return _rowcount(result)


async def revoke_session_by_id(db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID, reason: str) -> bool:
    """Revoke one session owned by the given user. Returns True if revoked now."""
    result = await db.execute(select(AuthSession).where(AuthSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None or session.user_id != user_id:
        return False
    if session.revoked_at is not None:
        return True  # already revoked; treat as success without leaking state
    session.revoked_at = _utcnow()
    session.revoke_reason = reason
    await db.flush()
    return True


async def revoke_all_user_sessions(
    db: AsyncSession, *, user_id: uuid.UUID, reason: str, except_session_id: uuid.UUID | None = None
) -> int:
    """Revoke every active session for the user, optionally keeping one alive."""
    query = (
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_utcnow(), revoke_reason=reason)
    )
    if except_session_id is not None:
        query = query.where(AuthSession.id != except_session_id)
    result = await db.execute(query)
    await db.flush()
    return _rowcount(result)


async def list_user_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> list[AuthSession]:
    result = await db.execute(
        select(AuthSession).where(AuthSession.user_id == user_id).order_by(AuthSession.created_at.desc()).limit(100)
    )
    return list(result.scalars().all())


async def change_password(
    db: AsyncSession,
    settings: Settings,
    *,
    user: User,
    current_password: str,
    new_password: str,
    keep_session_id: uuid.UUID | None,
) -> None:
    validate_password_strength(new_password, min_length=settings.password_min_length)
    if not verify_password(current_password, user.hashed_password):
        raise LoginFailure("invalid_password")
    user.hashed_password = hash_password(new_password)
    await revoke_all_user_sessions(
        db,
        user_id=user.id,
        reason=REVOKE_REASON_PASSWORD_CHANGE,
        except_session_id=keep_session_id,
    )


async def create_password_reset_request(
    db: AsyncSession, settings: Settings, *, email: str, ip_address: str | None
) -> str | None:
    """Create a single-use reset token. Returns the raw token, or None when the
    account does not exist or is disabled (callers must respond identically)."""
    user = await _get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None

    # Single active reset token per user: invalidate previous unused ones.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(expires_at=_utcnow())
    )

    raw_token = generate_reset_token()
    now = _utcnow()
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.password_reset_token_expire_minutes),
        requested_ip=ip_address,
    )
    db.add(record)
    await db.flush()
    return raw_token


async def consume_password_reset_token(
    db: AsyncSession, settings: Settings, *, raw_token: str, new_password: str
) -> User | None:
    """Atomically consume a reset token and set the new password.

    Returns the user on success, None when the token is invalid/expired/used.
    """
    validate_password_strength(new_password, min_length=settings.password_min_length)

    token_hash = hash_reset_token(raw_token)
    now = _utcnow()

    # Atomic single-use consumption: only one concurrent request can flip used_at.
    # Expiry is checked in Python afterwards (driver-agnostic datetime handling).
    result = await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    if not _rowcount(result):
        return None

    select_result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    record = select_result.scalar_one()
    if _as_utc(record.expires_at) <= now:
        return None

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    user.hashed_password = hash_password(new_password)
    await revoke_all_user_sessions(db, user_id=user.id, reason=REVOKE_REASON_PASSWORD_RESET)
    return user


def session_to_dict(session: AuthSession, current_session_id: uuid.UUID | None) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_used_at": session.last_used_at.isoformat() if session.last_used_at else None,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "revoked": session.revoked_at is not None,
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "current": current_session_id is not None and session.id == current_session_id,
    }
