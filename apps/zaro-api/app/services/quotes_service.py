"""Quotes service: creation, snapshot math, lifecycle transitions.

State machine (models.enums.QUOTE_TRANSITIONS)::

    draft ──► sent ──► viewed ──► accepted ──► deposit_required ──► converted
                 │        │
                 ▼        ▼
             rejected  rejected
                 │        │
                 └────────┴──► cancelled   (from draft/sent/viewed)

    expired: lazy terminal state -- a sent/viewed quote past its
    ``valid_until`` is treated as expired by every mutating operation and is
    persisted as EXPIRED by :func:`expire_if_past_validity`.

All money math uses the deterministic Money abstraction (integer minor
units, Decimal quantities, ROUND_HALF_UP). Client-supplied amounts are never
trusted: totals and deposits are recomputed here from line inputs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateTransition, NotFoundError, ValidationFailedError
from app.core.money import Currency, Money, validate_amount_minor
from app.models.customer import Customer
from app.models.enums import QUOTE_TRANSITIONS, QuoteStatus
from app.models.quote import Quote, QuoteLine


@dataclass(frozen=True, slots=True)
class QuoteLineInput:
    """Validated line input for quote creation."""

    description: str
    quantity: Decimal
    unit_label: str | None
    unit_price_minor: int

    @classmethod
    def build(
        cls,
        *,
        description: str,
        quantity: str | int | Decimal,
        unit_label: str | None,
        unit_price_minor: int,
    ) -> QuoteLineInput:
        if not description or not description.strip():
            raise ValidationFailedError("quote line description is required")
        if len(description) > 300:
            raise ValidationFailedError("quote line description too long")
        if isinstance(quantity, bool | float):
            raise ValidationFailedError("quantity must be a decimal string or integer")
        try:
            qty = Decimal(str(quantity))
        except InvalidOperation as exc:
            raise ValidationFailedError("invalid quantity") from exc
        if not qty.is_finite() or qty <= 0 or qty > Decimal("1000000"):
            raise ValidationFailedError("quantity must be a positive value")
        return cls(
            description=description.strip(),
            quantity=qty,
            unit_label=unit_label,
            unit_price_minor=validate_amount_minor(unit_price_minor, field="unit_price", allow_zero=True),
        )


async def get_quote(db: AsyncSession, quote_id: uuid.UUID) -> Quote:
    quote = await db.get(Quote, quote_id)
    if quote is None:
        raise NotFoundError("Quote not found")
    return quote


async def get_quote_for_update(db: AsyncSession, quote_id: uuid.UUID) -> Quote:
    """Load and row-lock a quote for a mutating decision (accept/reject/send/cancel/view).

    Serializes concurrent decisions on the same quote so exactly one wins;
    the loser observes the already-moved state and fails with a clean 4xx
    instead of double-converting or double-auditing.
    """
    stmt = select(Quote).where(Quote.id == quote_id).with_for_update()
    quote = (await db.execute(stmt)).scalar_one_or_none()
    if quote is None:
        raise NotFoundError("Quote not found")
    return quote


async def get_lines(db: AsyncSession, quote_id: uuid.UUID) -> list[QuoteLine]:
    stmt = select(QuoteLine).where(QuoteLine.quote_id == quote_id).order_by(QuoteLine.position)
    return list((await db.execute(stmt)).scalars().all())


async def get_default_deposit_percentage(db: AsyncSession) -> int:
    """Read the configured default deposit policy."""
    from app.services.payments_service import get_configuration

    config = await get_configuration(db)
    return config.default_deposit_percentage


def compute_totals(
    lines: list[QuoteLineInput],
    *,
    discount_minor: int,
    delivery_fee_minor: int,
    deposit_percentage: int,
) -> tuple[dict[str, int], list[int]]:
    """Deterministically compute subtotal/discount/delivery/total/deposit/balance.

    This is the single authoritative pricing path shared by quotes and
    orders. Returns (totals-by-name, per-line computed totals).
    """
    validate_amount_minor(discount_minor, field="discount")
    validate_amount_minor(delivery_fee_minor, field="delivery_fee")
    if not 0 <= deposit_percentage <= 100:
        raise ValidationFailedError("deposit_percentage must be between 0 and 100")

    subtotal = Money.zero(Currency.DZD)
    line_totals: list[int] = []
    for line in lines:
        amount = Money(line.unit_price_minor, Currency.DZD).multiply(line.quantity)
        line_totals.append(amount.amount_minor)
        subtotal += amount

    discount = Money(discount_minor, Currency.DZD)
    if subtotal < discount:
        raise ValidationFailedError("discount cannot exceed the subtotal")
    delivery_fee = Money(delivery_fee_minor, Currency.DZD)
    total = subtotal - discount + delivery_fee
    deposit_amount = total.percentage(deposit_percentage)
    balance = total - deposit_amount  # percentage() guarantees deposit <= total

    totals = {
        "subtotal_minor": subtotal.amount_minor,
        "discount_minor": discount.amount_minor,
        "delivery_fee_minor": delivery_fee.amount_minor,
        "total_minor": total.amount_minor,
        "deposit_amount_minor": deposit_amount.amount_minor,
        "balance_amount_minor": balance.amount_minor,
    }
    return totals, line_totals


async def create_quote(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID | None,
    custom_request_id: uuid.UUID | None,
    lines: list[QuoteLineInput],
    discount_minor: int = 0,
    delivery_fee_minor: int = 0,
    deposit_percentage: int | None = None,
    valid_until: datetime,
    notes: str | None = None,
    created_by: uuid.UUID | None = None,
) -> Quote:
    if not lines:
        raise ValidationFailedError("A quote requires at least one line item")
    if valid_until.tzinfo is None:
        raise ValidationFailedError("valid_until must be timezone-aware")
    if valid_until <= datetime.now(UTC):
        raise ValidationFailedError("valid_until must be in the future")

    if customer_id is not None:
        customer = await db.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")

    pct = deposit_percentage if deposit_percentage is not None else await get_default_deposit_percentage(db)
    totals, line_totals = compute_totals(
        lines,
        discount_minor=discount_minor,
        delivery_fee_minor=delivery_fee_minor,
        deposit_percentage=pct,
    )

    from app.services.references import next_quote_number, run_with_unique_retry

    async def _insert() -> Quote:
        candidate = Quote(
            quote_number=await next_quote_number(db),
            customer_id=customer_id,
            custom_request_id=custom_request_id,
            status=QuoteStatus.DRAFT,
            currency="DZD",
            subtotal_minor=totals["subtotal_minor"],
            discount_minor=totals["discount_minor"],
            delivery_fee_minor=totals["delivery_fee_minor"],
            total_minor=totals["total_minor"],
            deposit_percentage=pct,
            deposit_amount_minor=totals["deposit_amount_minor"],
            balance_amount_minor=totals["balance_amount_minor"],
            notes=notes,
            valid_until=valid_until,
            created_by=created_by,
        )
        db.add(candidate)
        await db.flush()

        for position, (line, line_total) in enumerate(zip(lines, line_totals, strict=True)):
            db.add(
                QuoteLine(
                    quote_id=candidate.id,
                    position=position,
                    description=line.description,
                    quantity=line.quantity,
                    unit_label=line.unit_label,
                    unit_price_minor=line.unit_price_minor,
                    line_total_minor=line_total,
                )
            )
        await db.flush()
        return candidate

    # Concurrent creations may compute the same quote number; retry with a
    # regenerated number instead of failing with a 500.
    return await run_with_unique_retry(db, _insert)


def validate_transition(current: QuoteStatus, target: QuoteStatus) -> None:
    allowed = QUOTE_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition quote from '{current.value}' to '{target.value}'",
            details={"current": current.value, "allowed": sorted(s.value for s in allowed)},
        )


def ensure_not_expired(quote: Quote) -> None:
    """Reject actions on quotes past ``valid_until``.

    Expiry is evaluated lazily at every mutating operation; the row itself is
    only persisted as EXPIRED by :func:`expire_if_past_validity`.
    """
    if quote.status in (
        QuoteStatus.SENT,
        QuoteStatus.VIEWED,
        QuoteStatus.ACCEPTED,
    ) and quote.valid_until <= datetime.now(UTC):
        raise InvalidStateTransition(
            "Quote has expired",
            details={"current": "expired", "allowed": []},
        )


async def change_status(db: AsyncSession, quote: Quote, target: QuoteStatus) -> Quote:
    current = QuoteStatus(quote.status)
    validate_transition(current, target)
    quote.status = target
    now = datetime.now(UTC)
    if target == QuoteStatus.SENT:
        quote.sent_at = now
    elif target == QuoteStatus.ACCEPTED:
        quote.accepted_at = now
    elif target == QuoteStatus.REJECTED:
        quote.rejected_at = now
    elif target == QuoteStatus.CANCELLED:
        quote.cancelled_at = now
    db.add(quote)
    await db.flush()
    return quote


async def mark_viewed(db: AsyncSession, quote: Quote) -> bool:
    """Record first customer view (sent -> viewed). Idempotent.

    Returns True when the row changed (callers audit QUOTE_VIEWED only then).
    """
    current = QuoteStatus(quote.status)
    if current == QuoteStatus.VIEWED:
        return False
    validate_transition(current, QuoteStatus.VIEWED)
    quote.status = QuoteStatus.VIEWED
    if quote.viewed_at is None:
        quote.viewed_at = datetime.now(UTC)
    db.add(quote)
    await db.flush()
    return True


async def expire_if_past_validity(db: AsyncSession, quote: Quote) -> bool:
    """Persist EXPIRED for an overdue non-terminal quote. True when changed."""
    if QuoteStatus(quote.status) not in (QuoteStatus.SENT, QuoteStatus.VIEWED, QuoteStatus.ACCEPTED):
        return False
    if quote.valid_until > datetime.now(UTC):
        return False
    quote.status = QuoteStatus.EXPIRED
    db.add(quote)
    await db.flush()
    return True
