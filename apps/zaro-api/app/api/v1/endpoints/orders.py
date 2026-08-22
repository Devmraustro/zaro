"""Order endpoints.

Orders are born server-side from accepted quotes; there is deliberately no
client-facing "create order" endpoint. Customers may view ONLY their own
orders/payments; staff access is permission-gated.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, get_current_user, require_permission
from app.core.exceptions import ForbiddenError
from app.core.rbac import has_permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import Permission
from app.models.order import Order
from app.models.user import User
from app.schemas.orders import OrderCancel
from app.schemas.payments import DepositClaimRequest
from app.services import orders_service, payments_service
from app.services.audit import record_event

router = APIRouter(tags=["orders"])
admin_router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


def _line_dicts(lines) -> list[dict[str, Any]]:
    return [
        {
            "id": str(line.id),
            "position": line.position,
            "description": line.description,
            "quantity": line.quantity,
            "unit_label": line.unit_label,
            "unit_price_minor": line.unit_price_minor,
            "line_total_minor": line.line_total_minor,
        }
        for line in lines
    ]


def serialize_public(order: Order, lines) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "quote_id": str(order.quote_id) if order.quote_id else None,
        "custom_request_id": str(order.custom_request_id) if order.custom_request_id else None,
        "status": str(order.status),
        "currency": order.currency,
        "subtotal_minor": order.subtotal_minor,
        "discount_minor": order.discount_minor,
        "delivery_fee_minor": order.delivery_fee_minor,
        "total_minor": order.total_minor,
        "deposit_required_minor": order.deposit_required_minor,
        "deposit_paid_minor": order.deposit_paid_minor,
        "balance_due_minor": order.balance_due_minor,
        "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "lines": _line_dicts(lines),
    }


def serialize_admin(order: Order, lines) -> dict[str, Any]:
    data = serialize_public(order, lines)
    data.update(
        {
            "customer_id": str(order.customer_id) if order.customer_id else None,
            "notes": order.notes,
            "cancellation_reason": order.cancellation_reason,
        }
    )
    return data


async def _staff_or_owner_order(db: AsyncSession, order_id: UUID, user: User, read_permission: Permission) -> Order:
    order = await orders_service.get_order(db, order_id)
    if user.role == "customer":
        customer = await orders_service.resolve_customer_for_user(db, user)
        if customer is None or order.customer_id != customer.id:
            raise ForbiddenError("You do not have access to this order")
        return order
    if not has_permission(user.role, read_permission):
        raise ForbiddenError("Insufficient permissions")
    return order


# --- Customer surface -----------------------------------------------------------


@router.get("/orders/mine")
async def list_my_orders(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    if user.role != "customer":
        raise ForbiddenError("This endpoint is for customer accounts")
    customer = await orders_service.resolve_customer_for_user(db, user)
    if customer is None:
        return []
    result = []
    for order in await orders_service.list_for_customer(db, customer.id):
        result.append(serialize_public(order, await orders_service.get_lines(db, order.id)))
    return result


@router.get("/orders/{order_id}")
async def get_my_order(
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    order = await _staff_or_owner_order(db, order_id, user, Permission.ORDERS_READ)
    return serialize_public(order, await orders_service.get_lines(db, order.id))


@router.get("/orders/{order_id}/payments")
async def list_order_payments(
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    order = await _staff_or_owner_order(db, order_id, user, Permission.PAYMENTS_READ)
    payments_list = await payments_service.list_for_orders(db, [order.id])
    from app.api.v1.endpoints.payments import serialize_public as serialize_payment

    return [serialize_payment(p) for p in payments_list]


@router.post("/orders/{order_id}/payments", status_code=201)
async def open_deposit_claim(
    request: Request,
    order_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _payload: DepositClaimRequest | None = None,
) -> dict[str, Any]:
    """Open the CCP deposit claim. Amount/reference/status are server-derived.

    `extra="forbid"` on DepositClaimRequest ensures any client-submitted
    fields (amount, status, etc.) are rejected with 422 instead of
    silently ignored.
    """
    order = await _staff_or_owner_order(db, order_id, user, Permission.PAYMENTS_REVIEW)
    payment = await payments_service.create_deposit_claim(
        db, order, customer_id=order.customer_id if order.customer_id is None else __import__("uuid").UUID(str(order.customer_id))
    )
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PAYMENT_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="payment",
        resource_id=str(payment.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "payment_reference": payment.payment_reference,
            "order_number": order.order_number,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "status": str(payment.status),
        },
    )
    await db.commit()
    from app.api.v1.endpoints.payments import serialize_public as serialize_payment

    return serialize_payment(payment)


# --- Admin surface --------------------------------------------------------------


@admin_router.get("")
async def list_orders_admin(
    _user: Annotated[User, Depends(require_permission(Permission.ORDERS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query(pattern=r"^(pending_deposit|confirmed|cancelled)$")] = None,
) -> dict[str, Any]:
    orders_list, total = await orders_service.list_admin(db, page=page, page_size=page_size, status=status)
    items = []
    for o in orders_list:
        items.append(serialize_admin(o, await orders_service.get_lines(db, o.id)))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@admin_router.get("/{order_id}")
async def get_order_admin(
    order_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.ORDERS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    order = await orders_service.get_order(db, order_id)
    return serialize_admin(order, await orders_service.get_lines(db, order.id))


@admin_router.post("/{order_id}/cancel")
async def cancel_order(
    request: Request,
    order_id: UUID,
    payload: OrderCancel,
    user: Annotated[User, Depends(require_permission(Permission.ORDERS_CANCEL))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    order = await orders_service.get_order(db, order_id)
    old_status = str(order.status)
    order = await orders_service.cancel_order(db, order, reason=payload.reason)

    # Any unresolved deposit claim is cancelled with the order (append-only:
    # the claim row stays, status moves to cancelled).
    active_claim = await payments_service.find_active_for_order(db, order.id)
    if active_claim is not None:
        from app.models.enums import PaymentStatus

        active_claim.status = PaymentStatus.CANCELLED
        db.add(active_claim)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.ORDER_CANCELLED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="order",
        resource_id=str(order.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"order_number": order.order_number, "old_status": old_status, "new_status": "cancelled"},
    )
    await db.commit()
    return serialize_admin(order, await orders_service.get_lines(db, order.id))
