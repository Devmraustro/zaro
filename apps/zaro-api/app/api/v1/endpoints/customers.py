"""Admin customers endpoints.

Customer PII is permission-gated per the RBAC matrix. CONTENT has no
access by design; WORKER/PRODUCTION have no access either.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, require_permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import Permission
from app.models.user import User
from app.schemas.customers import CustomerCreate, CustomerUpdate
from app.services import customers_service
from app.services.audit import record_event

router = APIRouter(prefix="/admin/customers", tags=["customers"])


def _serialize_customer(customer) -> dict[str, Any]:
    return {
        "id": str(customer.id),
        "full_name": customer.full_name,
        "email": customer.email,
        "phone": customer.phone,
        "company_name": customer.company_name,
        "address": customer.address,
        "city": customer.city,
        "municipality": customer.municipality,
        "notes": customer.notes,
        "status": str(customer.status),
        "user_id": str(customer.user_id) if customer.user_id else None,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }


@router.post("", status_code=201)
async def create_customer(
    payload: CustomerCreate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMERS_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    customer = await customers_service.create_customer(db, payload.model_dump(exclude_unset=True))
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.CUSTOMER_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="customer",
        resource_id=str(customer.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return _serialize_customer(customer)


@router.get("")
async def list_customers(
    _user: Annotated[User, Depends(require_permission(Permission.CUSTOMERS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> dict[str, Any]:
    customers, total = await customers_service.list_customers(db, page=page, page_size=page_size, search=search)
    return {
        "items": [_serialize_customer(c) for c in customers],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/{customer_id}")
async def get_customer(
    customer_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.CUSTOMERS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    customer = await customers_service.get_customer(db, customer_id)
    return _serialize_customer(customer)


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMERS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    customer = await customers_service.get_customer(db, customer_id)
    changes = payload.model_dump(exclude_unset=True)
    customer = await customers_service.update_customer(db, customer, changes)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.CUSTOMER_UPDATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="customer",
        resource_id=str(customer.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"fields": sorted(changes.keys())},
    )
    await db.commit()
    return _serialize_customer(customer)
