from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.rate_limit import get_client_ip
from app.core.rbac import has_permission
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import Permission, Role
from app.models.user import User
from app.services.audit import record_event

logger = get_logger("app.api.deps")


def _get_request_context(request: Request) -> tuple[str | None, str | None, str | None]:
    """Extract request_id, ip_address, user_agent from request.

    The client IP honours X-Forwarded-For only when the direct peer is an
    explicitly configured trusted proxy (see rate_limit.get_client_ip).
    """
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = request.headers.get("X-Request-ID")

    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
    ip_address = get_client_ip(request, settings)

    user_agent = request.headers.get("User-Agent")
    return request_id, ip_address, user_agent


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
    db: Annotated[AsyncSession, Depends(get_db)] = None,  # type: ignore[assignment]
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid authorization header")
    token = authorization[7:]
    payload = decode_access_token(settings, token)
    # Stash claims so downstream dependencies/endpoints can read session id
    # without decoding the token a second time.
    request.state.token_payload = payload
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")
    try:
        user_uuid = UUID(user_id)
    except (ValueError, AttributeError, TypeError):
        raise UnauthorizedError("Invalid token payload") from None
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise UnauthorizedError("User account is disabled")
    return user


def get_current_session_id(request: Request) -> UUID | None:
    """Session id embedded in the current access token, when present."""
    payload = getattr(request.state, "token_payload", None)
    sid = payload.get("sid") if isinstance(payload, dict) else None
    if not sid:
        return None
    try:
        return UUID(str(sid))
    except ValueError:
        return None


def require_permission(permission: Permission):
    """FastAPI dependency factory that enforces a specific permission.

    Usage::

        @router.get("/orders")
        async def list_orders(
            _user: Annotated[User, Depends(require_permission(Permission.ORDERS_READ))],
        ):
            ...
    """

    async def _check(
        request: Request,
        response: Response,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> User:
        if not has_permission(current_user.role, permission):
            request_id, ip_address, user_agent = _get_request_context(request)
            await record_event(
                db,
                action=AuditAction.PERMISSION_DENIED,
                result=AuditResult.DENIED,
                actor_user_id=current_user.id,
                resource_type=permission.value.split(".")[0],
                resource_id=None,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "required_permission": permission.value,
                    "user_role": current_user.role.value
                    if hasattr(current_user.role, "value")
                    else str(current_user.role),
                },
            )
            await db.commit()
            raise ForbiddenError("Insufficient permissions")
        return current_user

    return _check


async def require_owner(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    role = Role(current_user.role) if isinstance(current_user.role, str) else current_user.role
    if role != Role.OWNER:
        raise ForbiddenError("Owner access required")
    return current_user


async def require_admin_or_owner(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    role = Role(current_user.role) if isinstance(current_user.role, str) else current_user.role
    if role not in (Role.OWNER, Role.ADMIN):
        raise ForbiddenError("Admin or owner access required")
    return current_user
