"""Quote endpoints.

Surfaces:

1. ``/admin/quotes`` -- staff: create draft quotes from commercial terms,
   list/detail, send, cancel. Amounts are never accepted from clients;
   totals/deposits are computed server-side from line inputs.
2. ``/quotes`` -- customers act ONLY on their own quotes: view (records
   first view), accept, reject. Acceptance atomically creates the order and
   moves the quote to deposit_required.
"""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, get_current_user, require_permission
from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.core.rbac import has_permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import Permission, QuoteStatus
from app.models.quote import Quote
from app.models.user import User
from app.schemas.quotes import QuoteAction, QuoteCreate
from app.services import orders_service, quotes_service
from app.services.audit import record_event

router = APIRouter(tags=["quotes"])
admin_router = APIRouter(prefix="/admin/quotes", tags=["admin-quotes"])


def _is_expired(quote: Quote) -> bool:
    return (
        quote.status in (QuoteStatus.SENT, QuoteStatus.VIEWED, QuoteStatus.ACCEPTED)
        and quote.valid_until <= datetime.now(UTC)
    )


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


def serialize_public(quote: Quote, lines) -> dict[str, Any]:
    data = {
        "id": str(quote.id),
        "quote_number": quote.quote_number,
        "custom_request_id": str(quote.custom_request_id) if quote.custom_request_id else None,
        "status": str(QuoteStatus(quote.status)),
        "currency": quote.currency,
        "subtotal_minor": quote.subtotal_minor,
        "discount_minor": quote.discount_minor,
        "delivery_fee_minor": quote.delivery_fee_minor,
        "total_minor": quote.total_minor,
        "deposit_percentage": quote.deposit_percentage,
        "deposit_amount_minor": quote.deposit_amount_minor,
        "balance_amount_minor": quote.balance_amount_minor,
        "valid_until": quote.valid_until.isoformat(),
        "accepted_at": quote.accepted_at.isoformat() if quote.accepted_at else None,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
        "is_expired": _is_expired(quote),
        "lines": _line_dicts(lines),
    }
    return data


def serialize_admin(quote: Quote, lines) -> dict[str, Any]:
    data = serialize_public(quote, lines)
    data.update(
        {
            "customer_id": str(quote.customer_id) if quote.customer_id else None,
            "notes": quote.notes,
            "created_by": str(quote.created_by) if quote.created_by else None,
            "sent_at": quote.sent_at.isoformat() if quote.sent_at else None,
            "viewed_at": quote.viewed_at.isoformat() if quote.viewed_at else None,
            "rejected_at": quote.rejected_at.isoformat() if quote.rejected_at else None,
            "cancelled_at": quote.cancelled_at.isoformat() if quote.cancelled_at else None,
        }
    )
    return data


async def _resolve_customer(db: AsyncSession, user: User):
    return await orders_service.resolve_customer_for_user(db, user)


async def _staff_or_owner_quote(db: AsyncSession, quote_id: UUID, user: User) -> Quote:
    """Load a quote enforcing customer ownership vs staff permission."""
    quote = await quotes_service.get_quote(db, quote_id)
    if user.role == "customer":
        customer = await _resolve_customer(db, user)
        if customer is None or quote.customer_id != customer.id:
            raise ForbiddenError("You do not have access to this quote")
        return quote
    if not has_permission(user.role, Permission.QUOTES_READ):
        raise ForbiddenError("Insufficient permissions")
    return quote


# --- Customer surface -----------------------------------------------------------


@router.get("/quotes/mine")
async def list_my_quotes(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    if user.role != "customer":
        raise ForbiddenError("This endpoint is for customer accounts")
    customer = await _resolve_customer(db, user)
    if customer is None:
        return []
    stmt = select(Quote).where(Quote.customer_id == customer.id).order_by(Quote.created_at.desc())
    quotes_list = list((await db.execute(stmt)).scalars().all())
    result = []
    for q in quotes_list:
        result.append(serialize_public(q, await quotes_service.get_lines(db, q.id)))
    return result


@router.get("/quotes/{quote_id}")
async def get_my_quote(
    request: Request,
    quote_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    quote = await _staff_or_owner_quote(db, quote_id, user)
    lines = await quotes_service.get_lines(db, quote.id)

    # First view by the OWNING customer records QUOTE_VIEWED once.
    if user.role == "customer" and QuoteStatus(quote.status) == QuoteStatus.SENT:
        if await quotes_service.expire_if_past_validity(db, quote):
            pass  # expired before viewing; no VIEWED event
        elif await quotes_service.mark_viewed(db, quote):
            request_id_ctx, ip_address, user_agent = _get_request_context(request)
            await record_event(
                db,
                action=AuditAction.QUOTE_VIEWED,
                result=AuditResult.SUCCESS,
                actor_user_id=user.id,
                resource_type="quote",
                resource_id=str(quote.id),
                request_id=request_id_ctx,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"quote_number": quote.quote_number},
            )
            await db.commit()
    return serialize_public(quote, lines)


async def _customer_decision(
    request: Request,
    quote_id: UUID,
    user: User,
    db: AsyncSession,
    target: QuoteStatus,
) -> tuple[Quote, dict[str, Any]]:
    """Shared accept/reject path with ownership + expiry enforcement."""
    quote = await quotes_service.get_quote(db, quote_id)
    if user.role == "customer":
        customer = await _resolve_customer(db, user)
        if customer is None or quote.customer_id != customer.id:
            raise ForbiddenError("You do not have access to this quote")
    else:
        if not has_permission(user.role, Permission.QUOTES_APPROVE):
            raise ForbiddenError("Insufficient permissions")

    expired = await quotes_service.expire_if_past_validity(db, quote)
    if expired:
        request_id_ctx, ip_address, user_agent = _get_request_context(request)
        await record_event(
            db,
            action=AuditAction.QUOTE_EXPIRED,
            result=AuditResult.SUCCESS,
            actor_user_id=user.id,
            resource_type="quote",
            resource_id=str(quote.id),
            request_id=request_id_ctx,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"quote_number": quote.quote_number},
        )
        await db.commit()
        raise ValidationFailedError("Quote has expired")

    quotes_service.ensure_not_expired(quote)
    old_status = str(QuoteStatus(quote.status))
    quote = await quotes_service.change_status(db, quote, target)
    return quote, {"old_status": old_status}


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(
    request: Request,
    quote_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _payload: QuoteAction | None = None,
) -> dict[str, Any]:
    quote, ctx = await _customer_decision(request, quote_id, user, db, QuoteStatus.ACCEPTED)

    # Server-side conversion: ACCEPTED -> DEPOSIT_REQUIRED + order snapshot.
    order = await orders_service.create_from_quote(db, quote)

    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.QUOTE_ACCEPTED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="quote",
        resource_id=str(quote.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "quote_number": quote.quote_number,
            "old_status": ctx["old_status"],
            "new_status": str(QuoteStatus.DEPOSIT_REQUIRED),
            "amount_minor": quote.total_minor,
            "currency": quote.currency,
        },
    )
    await record_event(
        db,
        action=AuditAction.ORDER_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="order",
        resource_id=str(order.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "order_number": order.order_number,
            "total_minor": order.total_minor,
            "deposit_required_minor": order.deposit_required_minor,
            "currency": order.currency,
        },
    )
    await db.commit()

    lines = await quotes_service.get_lines(db, quote.id)
    return {
        "quote": serialize_public(quote, lines),
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "status": str(order.status),
            "deposit_required_minor": order.deposit_required_minor,
            "total_minor": order.total_minor,
            "balance_due_minor": order.balance_due_minor,
        },
    }


@router.post("/quotes/{quote_id}/reject")
async def reject_quote(
    request: Request,
    quote_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _payload: QuoteAction | None = None,
) -> dict[str, Any]:
    quote, ctx = await _customer_decision(request, quote_id, user, db, QuoteStatus.REJECTED)
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.QUOTE_REJECTED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="quote",
        resource_id=str(quote.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"quote_number": quote.quote_number, **ctx},
    )
    await db.commit()
    return serialize_public(quote, await quotes_service.get_lines(db, quote.id))


# --- Admin surface --------------------------------------------------------------


@admin_router.post("", status_code=201)
async def create_quote_endpoint(
    request: Request,
    payload: QuoteCreate,
    user: Annotated[User, Depends(require_permission(Permission.QUOTES_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    quote = await quotes_service.create_quote(
        db,
        customer_id=payload.customer_id,
        custom_request_id=payload.custom_request_id,
        lines=[line.to_input() for line in payload.lines],
        discount_minor=payload.discount_minor,
        delivery_fee_minor=payload.delivery_fee_minor,
        deposit_percentage=payload.deposit_percentage,
        valid_until=payload.valid_until,
        notes=payload.notes,
        created_by=user.id,
    )
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.QUOTE_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="quote",
        resource_id=str(quote.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "quote_number": quote.quote_number,
            "total_minor": quote.total_minor,
            "deposit_amount_minor": quote.deposit_amount_minor,
            "currency": quote.currency,
        },
    )
    await db.commit()
    return serialize_admin(quote, await quotes_service.get_lines(db, quote.id))


@admin_router.get("")
async def list_quotes_admin(
    _user: Annotated[User, Depends(require_permission(Permission.QUOTES_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[
        str | None,
        Query(pattern=r"^(draft|sent|viewed|accepted|deposit_required|converted|expired|cancelled|rejected)$"),
    ] = None,
) -> dict[str, Any]:
    from sqlalchemy import func

    stmt = select(Quote)
    count_stmt = select(func.count()).select_from(Quote)
    if status:
        stmt = stmt.where(Quote.status == status)
        count_stmt = count_stmt.where(Quote.status == status)
    stmt = stmt.order_by(Quote.created_at.desc())
    total = (await db.execute(count_stmt)).scalar_one()
    quotes_list = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())
    items = []
    for q in quotes_list:
        items.append(serialize_admin(q, await quotes_service.get_lines(db, q.id)))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@admin_router.get("/{quote_id}")
async def get_quote_admin(
    quote_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.QUOTES_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    quote = await quotes_service.get_quote(db, quote_id)
    return serialize_admin(quote, await quotes_service.get_lines(db, quote.id))


@admin_router.post("/{quote_id}/send")
async def send_quote(
    request: Request,
    quote_id: UUID,
    user: Annotated[User, Depends(require_permission(Permission.QUOTES_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    _payload: QuoteAction | None = None,
) -> dict[str, Any]:
    quote = await quotes_service.get_quote(db, quote_id)
    old_status = str(QuoteStatus(quote.status))
    quote = await quotes_service.change_status(db, quote, QuoteStatus.SENT)
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.QUOTE_SENT,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="quote",
        resource_id=str(quote.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"quote_number": quote.quote_number, "old_status": old_status, "new_status": "sent"},
    )
    await db.commit()
    return serialize_admin(quote, await quotes_service.get_lines(db, quote.id))


@admin_router.post("/{quote_id}/cancel")
async def cancel_quote(
    request: Request,
    quote_id: UUID,
    user: Annotated[User, Depends(require_permission(Permission.QUOTES_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    _payload: QuoteAction | None = None,
) -> dict[str, Any]:
    quote = await quotes_service.get_quote(db, quote_id)
    old_status = str(QuoteStatus(quote.status))
    quote = await quotes_service.change_status(db, quote, QuoteStatus.CANCELLED)
    request_id_ctx, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.QUOTE_CANCELLED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="quote",
        resource_id=str(quote.id),
        request_id=request_id_ctx,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"quote_number": quote.quote_number, "old_status": old_status, "new_status": "cancelled"},
    )
    await db.commit()
    return serialize_admin(quote, await quotes_service.get_lines(db, quote.id))
