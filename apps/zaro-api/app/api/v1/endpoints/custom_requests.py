"""Custom request endpoints.

Three surfaces with different trust levels:

1. ``POST /custom-requests`` -- public website form (no auth). Rate-limited
   per IP; creates/reuses a customer record and the request.
2. ``GET /custom-requests/mine`` -- authenticated customers see only their
   own requests (matched by account link or verified email).
3. ``/admin/custom-requests`` -- staff listing + lifecycle transitions,
   permission-gated and audited.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, get_current_user, require_permission
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, RateLimitError, ValidationFailedError
from app.core.rate_limit import get_client_ip, get_rate_limiter
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.customer import Customer
from app.models.enums import CustomRequestStatus, Permission
from app.models.user import User
from app.schemas.custom_requests import (
    CustomRequestStatusUpdate,
    CustomRequestSubmit,
)
from app.services import custom_requests_service
from app.services.audit import record_event

router = APIRouter(tags=["custom-requests"])
admin_router = APIRouter(prefix="/admin/custom-requests", tags=["admin-custom-requests"])


def _serialize_public(request_obj) -> dict[str, Any]:
    return {
        "id": str(request_obj.id),
        "reference": request_obj.reference,
        "product_type": request_obj.product_type,
        "description": request_obj.description,
        "desired_dimensions": request_obj.desired_dimensions,
        "materials": request_obj.materials,
        "colors": request_obj.colors,
        "finish": request_obj.finish,
        "quantity": request_obj.quantity,
        "budget_min_minor": request_obj.budget_min_minor,
        "budget_max_minor": request_obj.budget_max_minor,
        "currency": request_obj.currency,
        "status": str(request_obj.status),
        "created_at": request_obj.created_at.isoformat() if request_obj.created_at else None,
        "updated_at": request_obj.updated_at.isoformat() if request_obj.updated_at else None,
    }


def _serialize_admin(request_obj) -> dict[str, Any]:
    data = _serialize_public(request_obj)
    data.update(
        {
            "customer_id": str(request_obj.customer_id) if request_obj.customer_id else None,
            "customer_name": request_obj.customer_name,
            "customer_email": request_obj.customer_email,
            "customer_phone": request_obj.customer_phone,
            "notes": request_obj.notes,
            "source": str(request_obj.source),
            "assigned_to": str(request_obj.assigned_to) if request_obj.assigned_to else None,
        }
    )
    return data


# --- Public submission --------------------------------------------------------


@router.post("/custom-requests", status_code=201)
async def submit_custom_request(
    payload: CustomRequestSubmit,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    limiter = get_rate_limiter(settings)
    ip_address = get_client_ip(request, settings)
    hits = await limiter.hit("custom_request_ip", ip_address or "unknown", 5, 3600)
    if hits > 5:
        raise RateLimitError("Too many requests from this address. Try again later.")

    if (
        payload.budget_min_minor is not None
        and payload.budget_max_minor is not None
        and payload.budget_min_minor > payload.budget_max_minor
    ):
        raise ValidationFailedError("budget_min cannot exceed budget_max")

    custom_request = await custom_requests_service.submit_request(
        db,
        full_name=payload.full_name.strip(),
        email=str(payload.email).lower() if payload.email else None,
        phone=payload.phone,
        product_type=payload.product_type,
        description=payload.description.strip(),
        desired_dimensions=payload.desired_dimensions,
        materials=payload.materials,
        colors=payload.colors,
        finish=payload.finish,
        quantity=payload.quantity,
        budget_min_minor=payload.budget_min_minor,
        budget_max_minor=payload.budget_max_minor,
        source="website",
    )
    request_id, ctx_ip, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.CUSTOM_REQUEST_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=None,
        resource_type="custom_request",
        resource_id=str(custom_request.id),
        request_id=request_id,
        ip_address=ctx_ip,
        user_agent=user_agent,
        metadata={"reference": custom_request.reference},
    )
    await db.commit()
    return _serialize_public(custom_request)


# --- Customer self-service ----------------------------------------------------


async def _customer_for_user(db: AsyncSession, user: User) -> Customer | None:
    stmt = select(Customer).where(Customer.user_id == user.id)
    customer = (await db.execute(stmt)).scalar_one_or_none()
    if customer is not None:
        return customer
    # Fall back to email match for accounts created after the customer record.
    stmt = select(Customer).where(Customer.email == user.email.lower())
    return (await db.execute(stmt)).scalar_one_or_none()


@router.get("/custom-requests/mine")
async def list_my_custom_requests(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    if user.role == "customer":
        customer = await _customer_for_user(db, user)
        if customer is None:
            return []
        requests_list = await custom_requests_service.list_requests_for_customer(db, customer.id)
        return [_serialize_public(r) for r in requests_list]
    # Staff fall through to the admin listing only with the permission.
    from app.core.rbac import has_permission

    if not has_permission(user.role, Permission.CUSTOM_REQUESTS_READ):
        raise ForbiddenError("Insufficient permissions")
    requests_list, _total = await custom_requests_service.list_requests_admin(db, page=1, page_size=100)
    return [_serialize_admin(r) for r in requests_list]


@router.get("/custom-requests/{request_id}")
async def get_my_custom_request(
    request_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    custom_request = await custom_requests_service.get_request(db, request_id)
    if user.role == "customer":
        customer = await _customer_for_user(db, user)
        if customer is None or custom_request.customer_id != customer.id:
            raise ForbiddenError("You do not have access to this request")
        return _serialize_public(custom_request)
    from app.core.rbac import has_permission

    if not has_permission(user.role, Permission.CUSTOM_REQUESTS_READ):
        raise ForbiddenError("Insufficient permissions")
    return _serialize_admin(custom_request)


# --- Admin --------------------------------------------------------------------


@admin_router.get("")
async def list_custom_requests_admin(
    _user: Annotated[User, Depends(require_permission(Permission.CUSTOM_REQUESTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[
        str | None, Query(pattern=r"^(submitted|under_review|needs_information|quotation_pending|cancelled|converted)$")
    ] = None,
) -> dict[str, Any]:
    requests_list, total = await custom_requests_service.list_requests_admin(
        db, page=page, page_size=page_size, status=status
    )
    return {
        "items": [_serialize_admin(r) for r in requests_list],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@admin_router.patch("/{request_id}/status")
async def change_request_status(
    request_id: UUID,
    payload: CustomRequestStatusUpdate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOM_REQUESTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    custom_request = await custom_requests_service.get_request(db, request_id)
    old_status = CustomRequestStatus(custom_request.status)
    custom_request = await custom_requests_service.change_status(
        db, custom_request, CustomRequestStatus(payload.status), note=payload.note
    )
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.CUSTOM_REQUEST_STATUS_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="custom_request",
        resource_id=str(custom_request.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"old": old_status.value, "new": custom_request.status},
    )
    await db.commit()
    return _serialize_admin(custom_request)


@admin_router.get("/{request_id}")
async def get_custom_request_admin(
    request_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.CUSTOM_REQUESTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    custom_request = await custom_requests_service.get_request(db, request_id)
    return _serialize_admin(custom_request)
