"""Orders service: server-controlled creation from accepted quotes.

An order can ONLY be created by :func:`create_from_quote`, and only while a
quote is in ACCEPTED state. The unique constraint on ``orders.quote_id``
makes double conversion impossible at the database level.

Deposit accounting:

- ``deposit_required_minor`` is copied from the accepted quote snapshot;
- ``deposit_paid_minor`` only ever increases through
  :func:`apply_confirmed_deposit` (called inside the payment-confirmation
  transaction);
- ``balance_due_minor = total - deposit_paid`` at all times (DB-checked).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, InvalidStateTransition, NotFoundError, ValidationFailedError
from app.models.customer import Customer
from app.models.enums import ORDER_TRANSITIONS, OrderStatus, QuoteStatus
from app.models.order import Order, OrderLine
from app.models.quote import Quote


async def get_order(db: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    return order


async def get_order_for_update(db: AsyncSession, order_id: uuid.UUID) -> Order:
    """Load and row-lock an order for a mutating transition (cancel).

    Serializes cancellation against concurrent payment confirmation (which
    locks the same row): the loser observes the settled state and fails
    cleanly instead of overwriting CONFIRMED with CANCELLED or vice versa.
    """
    stmt = select(Order).where(Order.id == order_id).with_for_update()
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found")
    return order


async def get_lines(db: AsyncSession, order_id: uuid.UUID) -> list[OrderLine]:
    stmt = select(OrderLine).where(OrderLine.order_id == order_id).order_by(OrderLine.position)
    return list((await db.execute(stmt)).scalars().all())


def validate_transition(current: OrderStatus, target: OrderStatus) -> None:
    allowed = ORDER_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition order from '{current.value}' to '{target.value}'",
            details={"current": current.value, "allowed": sorted(s.value for s in allowed)},
        )


async def create_from_quote(db: AsyncSession, quote: Quote) -> Order:
    """Create the order for an accepted quote (idempotent per quote).

    Transitions the quote ACCEPTED -> DEPOSIT_REQUIRED within the caller's
    transaction. Raises ConflictError if an order already exists for this
    quote.
    """
    if QuoteStatus(quote.status) != QuoteStatus.ACCEPTED:
        raise InvalidStateTransition(
            "Orders can only be created from an accepted quote",
            details={"current": str(QuoteStatus(quote.status).value)},
        )

    existing = (await db.execute(select(Order).where(Order.quote_id == quote.id))).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("An order already exists for this quote")

    from app.services.quotes_service import get_lines as get_quote_lines
    from app.services.references import next_order_number, run_with_unique_retry

    lines = await get_quote_lines(db, quote.id)
    if not lines:
        raise ValidationFailedError("Quote has no line items")

    async def _insert() -> Order:
        candidate = Order(
            order_number=await next_order_number(db),
            customer_id=quote.customer_id,
            quote_id=quote.id,
            custom_request_id=quote.custom_request_id,
            status=OrderStatus.PENDING_DEPOSIT,
            currency="DZD",
            subtotal_minor=quote.subtotal_minor,
            discount_minor=quote.discount_minor,
            delivery_fee_minor=quote.delivery_fee_minor,
            total_minor=quote.total_minor,
            # Authoritative deposit copied from the quote snapshot; payments must
            # match it exactly.
            deposit_required_minor=quote.deposit_amount_minor,
            deposit_paid_minor=0,
            balance_due_minor=quote.total_minor,
            notes=quote.notes,
        )
        db.add(candidate)
        await db.flush()

        for position, ql in enumerate(lines):
            db.add(
                OrderLine(
                    order_id=candidate.id,
                    position=position,
                    description=ql.description,
                    quantity=ql.quantity,
                    unit_label=ql.unit_label,
                    unit_price_minor=ql.unit_price_minor,
                    line_total_minor=ql.line_total_minor,
                )
            )
        await db.flush()
        return candidate

    # Reference collisions regenerate-and-retry; a genuine double conversion
    # surfaces as 409 via the unique quote_id backstop.
    order = await run_with_unique_retry(db, _insert, conflict_message="An order already exists for this quote")

    # Quote moves forward: deposit now required from the customer.
    quote.status = QuoteStatus.DEPOSIT_REQUIRED
    db.add(quote)
    await db.flush()
    return order


async def apply_confirmed_deposit(db: AsyncSession, order: Order, amount_minor: int) -> Order:
    """Account a confirmed deposit payment against the order.

    Must run inside the same transaction as the payment confirmation. The
    caller is responsible for having row-locked both rows.
    """
    if OrderStatus(order.status) != OrderStatus.PENDING_DEPOSIT:
        raise ConflictError("Order is not awaiting a deposit")
    new_paid = order.deposit_paid_minor + amount_minor
    if new_paid > order.total_minor:
        raise ValidationFailedError("Confirmed deposits cannot exceed the order total")

    order.deposit_paid_minor = new_paid
    order.balance_due_minor = order.total_minor - new_paid
    if new_paid >= order.deposit_required_minor:
        validate_transition(OrderStatus(order.status), OrderStatus.CONFIRMED)
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = datetime.now(UTC)

        # The originating quote completes its lifecycle with the order.
        # Locked: concurrent order cancellation links the same quote row.
        if order.quote_id is not None:
            locked = (
                await db.execute(select(Quote).where(Quote.id == order.quote_id).with_for_update())
            ).scalar_one_or_none()
            if locked is not None and QuoteStatus(locked.status) == QuoteStatus.DEPOSIT_REQUIRED:
                locked.status = QuoteStatus.CONVERTED
                db.add(locked)
    db.add(order)
    await db.flush()
    return order


async def cancel_order(db: AsyncSession, order: Order, *, reason: str | None = None) -> Order:
    """Cancel an order and unlink its lifecycle.

    Callers must pass a row-locked order (see :func:`get_order_for_update`)
    so cancellation serializes against concurrent payment confirmation.
    """
    current = OrderStatus(order.status)
    validate_transition(current, OrderStatus.CANCELLED)
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.now(UTC)
    if reason:
        order.cancellation_reason = reason[:500]
    db.add(order)
    await db.flush()

    # Cancel the originating quote too (accepted/deposit_required are not
    # directly cancellable; this is the documented server-side linkage).
    # Locked: concurrent payment confirmation links the same quote row.
    if order.quote_id is not None:
        locked = (
            await db.execute(select(Quote).where(Quote.id == order.quote_id).with_for_update())
        ).scalar_one_or_none()
        if locked is not None and QuoteStatus(locked.status) in (QuoteStatus.ACCEPTED, QuoteStatus.DEPOSIT_REQUIRED):
            locked.status = QuoteStatus.CANCELLED
            locked.cancelled_at = datetime.now(UTC)
            db.add(locked)
    return order


async def list_for_customer(db: AsyncSession, customer_id: uuid.UUID) -> list[Order]:
    stmt = select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def list_admin(
    db: AsyncSession, *, page: int, page_size: int, status: str | None = None
) -> tuple[list[Order], int]:
    stmt = select(Order)
    count_stmt = select(func.count()).select_from(Order)
    if status:
        stmt = stmt.where(Order.status == status)
        count_stmt = count_stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc())
    total = (await db.execute(count_stmt)).scalar_one()
    orders = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())
    return orders, total


async def resolve_customer_for_user(db: AsyncSession, user) -> Customer | None:
    """Link an account to its customer record (by id link, then email)."""
    stmt = select(Customer).where(Customer.user_id == user.id)
    customer = (await db.execute(stmt)).scalar_one_or_none()
    if customer is not None:
        return customer
    stmt = select(Customer).where(Customer.email == user.email.lower())
    return (await db.execute(stmt)).scalar_one_or_none()
