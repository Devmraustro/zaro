"""Payments service: manual CCP deposit claims with human verification.

ZARO has NO bank/CCP API integration. A payment row is a customer's claim
that they made a manual transfer; an authorized operator verifies the
uploaded proof. Nothing in this module should ever be described as
automatic or bank-verified payment.

Concurrency: :func:`confirm_payment` row-locks the payment and its order
(``SELECT ... FOR UPDATE``) so two simultaneous confirmations serialize --
the loser sees the row already CONFIRMED and fails with 409. On PostgreSQL
partial unique indexes additionally guarantee one active/confirmed deposit
claim per order.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, InvalidStateTransition, NotFoundError, ValidationFailedError
from app.models.enums import PAYMENT_STATUS_TRANSITIONS, OrderStatus, PaymentMethod, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment, PaymentConfiguration

_ACTIVE_STATUSES = frozenset(
    {PaymentStatus.PENDING, PaymentStatus.PROOF_UPLOADED, PaymentStatus.UNDER_REVIEW}
)


# --- Configuration ------------------------------------------------------------


async def get_configuration(db: AsyncSession) -> PaymentConfiguration:
    """Return the singleton CCP configuration, creating defaults on first use."""
    config = (await db.execute(select(PaymentConfiguration).limit(1))).scalar_one_or_none()
    if config is None:
        config = PaymentConfiguration(
            account_holder="ZARO",
            account_identifier="",
            instructions=None,
            default_deposit_percentage=40,
        )
        db.add(config)
        await db.flush()
    return config


async def update_configuration(
    db: AsyncSession,
    *,
    account_holder: str | None = None,
    account_identifier: str | None = None,
    instructions: str | None = None,
    default_deposit_percentage: int | None = None,
    updated_by: uuid.UUID | None = None,
) -> PaymentConfiguration:
    config = await get_configuration(db)
    if account_holder is not None:
        account_holder = account_holder.strip()
        if not 2 <= len(account_holder) <= 200:
            raise ValidationFailedError("account_holder must be 2-200 characters")
        config.account_holder = account_holder
    if account_identifier is not None:
        account_identifier = account_identifier.strip()
        if not 1 <= len(account_identifier) <= 120:
            raise ValidationFailedError("account_identifier must be 1-120 characters")
        config.account_identifier = account_identifier
    if instructions is not None:
        if len(instructions) > 2000:
            raise ValidationFailedError("instructions must be at most 2000 characters")
        config.instructions = instructions.strip() or None
    if default_deposit_percentage is not None:
        if not isinstance(default_deposit_percentage, int) or not 0 <= default_deposit_percentage <= 100:
            raise ValidationFailedError("default_deposit_percentage must be an integer 0-100")
        if default_deposit_percentage == 0:
            raise ValidationFailedError("default_deposit_percentage must be greater than zero")
        config.default_deposit_percentage = default_deposit_percentage
    config.updated_by = updated_by
    db.add(config)
    await db.flush()
    return config


# --- Payments -------------------------------------------------------------------


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    return payment


async def get_for_update(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    """Row-lock a payment for a mutating transition."""
    stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Payment not found")
    return payment


async def find_active_for_order(db: AsyncSession, order_id: uuid.UUID) -> Payment | None:
    stmt = select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
    for payment in (await db.execute(stmt)).scalars().all():
        if PaymentStatus(payment.status) in _ACTIVE_STATUSES:
            return payment
    return None


async def create_deposit_claim(db: AsyncSession, order: Order, *, customer_id: uuid.UUID | None) -> Payment:
    """Open the deposit claim for an order awaiting its deposit.

    The amount is ALWAYS ``order.deposit_required_minor`` -- client input has
    no influence over it. Raises ConflictError when an unresolved claim
    already exists (also enforced by a partial unique index on PostgreSQL).
    """
    if OrderStatus(order.status) != OrderStatus.PENDING_DEPOSIT:
        raise InvalidStateTransition(
            "Payments can only be opened for orders pending deposit",
            details={"current": str(OrderStatus(order.status).value)},
        )
    active = await find_active_for_order(db, order.id)
    if active is not None:
        raise ConflictError("A deposit claim already exists for this order")

    config = await get_configuration(db)
    if not config.account_identifier:
        raise ValidationFailedError("CCP payment instructions are not configured yet")

    from app.services.references import next_payment_reference

    payment = Payment(
        payment_reference=await next_payment_reference(db),
        order_id=order.id,
        customer_id=customer_id or order.customer_id,
        method=PaymentMethod.CCP,
        status=PaymentStatus.PENDING,
        amount_minor=order.deposit_required_minor,  # authoritative amount
        currency="DZD",
        ccp_account_holder_snapshot=config.account_holder,
        ccp_account_identifier_snapshot=config.account_identifier,
    )
    db.add(payment)
    await db.flush()
    return payment


def validate_transition(current: PaymentStatus, target: PaymentStatus) -> None:
    allowed = PAYMENT_STATUS_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition payment from '{current.value}' to '{target.value}'",
            details={"current": current.value, "allowed": sorted(s.value for s in allowed)},
        )


async def attach_proof(db: AsyncSession, payment: Payment, *, asset_id: uuid.UUID) -> Payment:
    """Attach/replace proof while the claim is unresolved or rejected.

    Attaching proof to a REJECTED payment moves it back to PROOF_UPLOADED
    (explicit resubmission path -- same record, no duplicate claims).
    """
    from datetime import UTC, datetime

    current = PaymentStatus(payment.status)
    validate_transition(current, PaymentStatus.PROOF_UPLOADED)
    payment.proof_asset_id = asset_id
    payment.proof_uploaded_at = datetime.now(UTC)
    if current == PaymentStatus.REJECTED:
        # Fresh review round clears the previous rejection context.
        payment.rejection_reason_code = None
        payment.rejection_reason_note = None
    payment.status = PaymentStatus.PROOF_UPLOADED
    db.add(payment)
    await db.flush()
    return payment


async def submit_for_review(db: AsyncSession, payment: Payment) -> Payment:
    """Customer asserts the transfer is done; proof becomes mandatory."""
    current = PaymentStatus(payment.status)
    validate_transition(current, PaymentStatus.UNDER_REVIEW)
    if payment.proof_asset_id is None:
        raise ValidationFailedError("A payment proof must be uploaded before review")
    from datetime import UTC, datetime

    payment.submitted_at = datetime.now(UTC)
    payment.status = PaymentStatus.UNDER_REVIEW
    db.add(payment)
    await db.flush()
    return payment


async def confirm_payment(db: AsyncSession, payment_id: uuid.UUID, *, reviewer_user_id: uuid.UUID) -> tuple[Payment, Order]:
    """Confirm a deposit payment and update the order -- atomically.

    Locking protocol (caller's transaction):

    1. row-lock the payment;
    2. verify it is UNDER_REVIEW, amount/currency match the authoritative
       deposit, and a proof exists;
    3. row-lock the order; verify it still awaits the deposit;
    4. apply the deposit to the order (may transition it to CONFIRMED and
       the originating quote to CONVERTED);
    5. mark the payment CONFIRMED with reviewer identity + timestamp.

    Two simultaneous confirmations serialize on the payment lock; the second
    observes CONFIRMED and fails safely. No double balance update can occur.
    """
    from app.services import orders_service

    payment = await get_for_update(db, payment_id)
    current = PaymentStatus(payment.status)
    if current != PaymentStatus.UNDER_REVIEW:
        raise ConflictError(
            "Payment is not awaiting review",
            details={"current": current.value},
        )
    if payment.proof_asset_id is None:
        raise ValidationFailedError("Payment has no proof attached")

    stmt = select(Order).where(Order.id == payment.order_id).with_for_update()
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found")

    # Amount/currency re-verification against the authoritative values.
    if payment.amount_minor != order.deposit_required_minor:
        raise ConflictError("Payment amount does not match the required deposit")
    if payment.currency != order.currency:
        raise ConflictError("Currency mismatch between payment and order")
    if OrderStatus(order.status) != OrderStatus.PENDING_DEPOSIT:
        raise ConflictError("Order is no longer awaiting a deposit")

    order = await orders_service.apply_confirmed_deposit(db, order, payment.amount_minor)

    from datetime import UTC, datetime

    payment.status = PaymentStatus.CONFIRMED
    payment.reviewed_at = datetime.now(UTC)
    payment.reviewed_by = reviewer_user_id
    db.add(payment)
    await db.flush()
    return payment, order


async def reject_payment(
    db: AsyncSession,
    payment: Payment,
    *,
    reason_code: str,
    reason_note: str | None,
    reviewer_user_id: uuid.UUID,
) -> Payment:
    current = PaymentStatus(payment.status)
    validate_transition(current, PaymentStatus.REJECTED)
    from datetime import UTC, datetime

    payment.status = PaymentStatus.REJECTED
    payment.rejection_reason_code = reason_code
    payment.rejection_reason_note = (reason_note or "").strip()[:500] or None
    payment.reviewed_at = datetime.now(UTC)
    payment.reviewed_by = reviewer_user_id
    db.add(payment)
    await db.flush()
    return payment


REJECTION_REASON_CODES = frozenset(
    {
        "proof_unreadable",
        "incorrect_amount",
        "incorrect_recipient",
        "duplicate_transfer",
        "invalid_proof",
        "other",
    }
)


async def list_payments_admin(
    db: AsyncSession, *, page: int, page_size: int, status: str | None = None
) -> tuple[list[Payment], int]:
    from sqlalchemy import func

    stmt = select(Payment)
    count_stmt = select(func.count()).select_from(Payment)
    if status:
        stmt = stmt.where(Payment.status == status)
        count_stmt = count_stmt.where(Payment.status == status)
    stmt = stmt.order_by(Payment.created_at.desc())
    total = (await db.execute(count_stmt)).scalar_one()
    payments = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())
    return payments, total


async def list_for_orders(db: AsyncSession, order_ids: list[uuid.UUID]) -> list[Payment]:
    if not order_ids:
        return []
    stmt = select(Payment).where(Payment.order_id.in_(order_ids)).order_by(Payment.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())
