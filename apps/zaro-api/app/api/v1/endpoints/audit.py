from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.enums import Permission
from app.models.user import User
from app.schemas.common import PaginationResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_audit_logs(
    _user: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    action: str | None = None,
    actor_id: UUID | None = None,
    result: str | None = None,
    resource_type: str | None = None,
) -> PaginationResponse:
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if actor_id:
        query = query.where(AuditLog.actor_user_id == actor_id)
        count_query = count_query.where(AuditLog.actor_user_id == actor_id)
    if result:
        query = query.where(AuditLog.result == result)
        count_query = count_query.where(AuditLog.result == result)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)
    result_set = await db.execute(query)
    logs = result_set.scalars().all()

    items = [
        {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "result": log.result,
            "request_id": log.request_id,
            "ip_address": log.ip_address,
            "metadata": log.metadata_json,
        }
        for log in logs
    ]

    return PaginationResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total,
        has_previous=page > 1,
    )
