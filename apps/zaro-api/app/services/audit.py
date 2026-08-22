"""Centralized audit logging service.

All audit events flow through this service.
Business modules call record_event() instead of duplicating database logic.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_enums import AuditAction, AuditResult
from app.models.audit_log import AuditLog

logger = get_logger("app.services.audit")

# Metadata size limits
MAX_METADATA_STRING_LENGTH = 1000
MAX_METADATA_DEPTH = 3
MAX_METADATA_SIZE_BYTES = 10000


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate and sanitize audit metadata. Removes secrets and enforces limits."""
    if not metadata:
        return None

    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if key.lower() in BLOCKED_KEYS:
            sanitized[key] = "[REDACTED]"
            continue
        if isinstance(value, str):
            sanitized[key] = value[:MAX_METADATA_STRING_LENGTH]
        elif isinstance(value, (int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_nested_dict(value, depth=1)
        elif isinstance(value, list) and len(value) <= 10:
            sanitized[key] = [
                _sanitize_nested_dict(v, depth=1) if isinstance(v, dict) else str(v)[:MAX_METADATA_STRING_LENGTH]
                for v in value
            ]
        else:
            sanitized[key] = str(value)[:MAX_METADATA_STRING_LENGTH]

    return sanitized


BLOCKED_KEYS = frozenset(
    {
        "password",
        "hashed_password",
        "secret",
        "secret_key",
        "encryption_key",
        "api_key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "credit_card",
        "card_number",
        "cvv",
        "ssn",
    }
)


def _sanitize_nested_dict(d: dict[str, Any], depth: int = 1) -> dict[str, Any]:
    if depth > MAX_METADATA_DEPTH:
        return {"_truncated": True}
    result: dict[str, Any] = {}
    for key, value in d.items():
        if key.lower() in BLOCKED_KEYS:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _sanitize_nested_dict(value, depth + 1)
        elif isinstance(value, str):
            result[key] = value[:MAX_METADATA_STRING_LENGTH]
        else:
            result[key] = str(value)[:MAX_METADATA_STRING_LENGTH]
    return result


async def record_event(
    db: AsyncSession,
    *,
    action: AuditAction,
    result: AuditResult,
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an audit event. This is the single entry point for all audit logging."""
    sanitized_metadata = _sanitize_metadata(metadata)

    event = AuditLog(
        actor_user_id=actor_user_id,
        action=action.value,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result.value,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=sanitized_metadata,
    )
    db.add(event)
    await db.flush()

    logger.info(
        "audit_event",
        action=action.value,
        result=result.value,
        actor=str(actor_user_id) if actor_user_id else None,
        resource=f"{resource_type}:{resource_id}" if resource_type else None,
    )

    return event
