"""True-concurrency tests on real PostgreSQL (env-gated).

SQLite silently ignores ``SELECT ... FOR UPDATE`` and enforces no partial
unique indexes the way PostgreSQL does, so the locking/idempotency paths
can only be verified here. These tests run only when ``ZARO_TEST_PG_URL``
points at a scratch database whose name contains ``test`` (safety guard:
each test drops and recreates the whole schema). Without the variable they
SKIP with an explicit reason -- never counted as passed.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import ConflictError, InvalidStateTransition, ValidationFailedError
from app.core.security import hash_password
from app.db.base import Base
from app.models.customer import Customer
from app.models.enums import FilePurpose, FileVisibility, QuoteStatus, Role
from app.models.file_asset import FileAsset
from app.models.inventory import StockMovement
from app.models.material import Material
from app.models.order import Order
from app.models.payment import Payment, PaymentConfiguration
from app.models.production import ProductionMaterialReservation
from app.models.user import User
from app.services import (
    inventory_service,
    orders_service,
    payments_service,
    production_service,
    quotes_service,
)

PG_URL = os.environ.get("ZARO_TEST_PG_URL", "")


def _pg_db_name(url: str) -> str:
    path = urlparse(url).path or ""
    query = urlparse(url).query or ""
    if path.strip("/"):
        return path.strip("/")
    for part in query.split("&"):
        if part.startswith("dbname="):
            return part.split("=", 1)[1]
    return ""


def _pg_reason() -> str | None:
    if not PG_URL:
        return "ZARO_TEST_PG_URL not set (PostgreSQL concurrency tests require a live server)"
    if "test" not in _pg_db_name(PG_URL).lower():
        return f"refusing to run destructive PG tests against non-test database '{_pg_db_name(PG_URL)}'"
    return None


pytestmark = pytest.mark.skipif(_pg_reason() is not None, reason=_pg_reason() or "")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def pg_session_factory():
    # Function-scoped: each test gets a fresh engine on its own event loop
    # plus a clean schema (drop + create isolates the concurrency trials).
    engine = create_async_engine(PG_URL, pool_size=8, max_overflow=0)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_material(db, code="PG-STL-01"):
    mat = Material(name="PG Steel", code=code, category="steel", unit="kg", is_active=True)
    db.add(mat)
    await db.commit()
    await inventory_service.purchase(db, material_id=mat.id, quantity=Decimal("100"), idempotency_key=uuid.uuid4())
    await db.commit()
    return mat


async def _seed_inspector(db, email):
    user = User(
        email=email,
        hashed_password=hash_password("test-password-123"),
        full_name="Inspector",
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _confirmed_order(db, email):
    customer = Customer(full_name="PG Customer", email=email)
    db.add(customer)
    await db.flush()
    quote = await quotes_service.create_quote(
        db,
        customer_id=customer.id,
        custom_request_id=None,
        lines=[
            quotes_service.QuoteLineInput.build(
                description="Widget", quantity=1, unit_label="pcs", unit_price_minor=20000
            )
        ],
        valid_until=datetime.now(UTC) + timedelta(days=7),
    )
    quote = await quotes_service.change_status(db, quote, QuoteStatus.SENT)
    quote = await quotes_service.change_status(db, quote, QuoteStatus.ACCEPTED)
    order = await orders_service.create_from_quote(db, quote)
    order = await orders_service.apply_confirmed_deposit(db, order, amount_minor=order.deposit_required_minor)
    await db.flush()
    return order


async def _started_production(db, order_id, material, required="10"):
    order = await db.get(Order, order_id)
    po = await production_service.create_production_order(db, order=order, created_by=None)
    await production_service.plan_production(
        db,
        production_order_id=po.id,
        requirements=[
            production_service.MaterialRequirement(
                material_id=material.id,
                material_name=material.name,
                material_code=material.code,
                material_unit=str(material.unit),
                quantity_required=Decimal(required),
                unit_price_minor=1000,
            )
        ],
    )
    await production_service.reserve_materials(db, po.id)
    await production_service.start_production(db, po.id)
    rows = (
        (
            await db.execute(
                select(ProductionMaterialReservation).where(ProductionMaterialReservation.production_order_id == po.id)
            )
        )
        .scalars()
        .all()
    )
    await db.flush()
    return po, rows[0]


@pytest.mark.anyio
async def test_concurrent_idempotent_consume_counts_once(pg_session_factory):
    """Two concurrent consumes with the same idempotency key: one movement, counted once."""
    sm = pg_session_factory
    async with sm() as db:
        mat = await _seed_material(db)
        order = await _confirmed_order(db, "t1@example.com")
        await db.commit()
        po, mr = await _started_production(db, order.id, mat)
        await db.commit()
        po_id, mr_id, mat_id = po.id, mr.id, mat.id

    key = uuid.uuid4()

    async def consume_once():
        async with sm() as db:
            try:
                await production_service.consume_material(
                    db,
                    production_order_id=po_id,
                    material_reservation_id=mr_id,
                    quantity=Decimal("4"),
                    idempotency_key=key,
                    actor_user_id=None,
                )
                await db.commit()
                return "ok"
            except Exception as exc:  # surfaced via result string for assertion
                await db.rollback()
                return f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(consume_once(), consume_once())
    assert results == ["ok", "ok"], results

    async with sm() as db:
        movements = (
            await db.execute(
                select(func.count()).select_from(StockMovement).where(StockMovement.idempotency_key == key)
            )
        ).scalar_one()
        fresh = await db.get(ProductionMaterialReservation, mr_id)
        level = await inventory_service.get_stock_level(db, mat_id)
    assert movements == 1
    assert fresh.quantity_consumed == Decimal("4")
    assert (level.on_hand, level.reserved) == (Decimal("96"), Decimal("6"))


@pytest.mark.anyio
async def test_concurrent_qc_decisions_single_winner(pg_session_factory):
    """Two concurrent QC decisions: exactly one applies, the other is rejected."""
    sm = pg_session_factory
    async with sm() as db:
        mat = await _seed_material(db, code="PG-STL-QC")
        insp = await _seed_inspector(db, "qc1@example.com")
        insp2 = await _seed_inspector(db, "qc2@example.com")
        order = await _confirmed_order(db, "t2@example.com")
        await db.commit()
        po, mr = await _started_production(db, order.id, mat)
        await production_service.consume_material(
            db,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("10"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=None,
        )
        await production_service.start_quality_check(db, po.id, inspector_id=insp.id)
        await db.commit()
        po_id = po.id
        insp_ids = (insp.id, insp2.id)

    async def decide(approved, inspector_id):
        async with sm() as db:
            try:
                done = await production_service.complete_quality_check(
                    db, po_id, approved=approved, inspector_id=inspector_id
                )
                await db.commit()
                return f"ok:{done.status}"
            except InvalidStateTransition:
                await db.rollback()
                return "InvalidStateTransition"
            except Exception as exc:  # surfaced via result string for assertion
                await db.rollback()
                return f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(decide(True, insp_ids[0]), decide(False, insp_ids[1]))
    assert sorted(results) in (
        ["InvalidStateTransition", "ok:in_production"],
        ["InvalidStateTransition", "ok:ready"],
    ), results


@pytest.mark.anyio
async def test_concurrent_oversell_cannot_overconsume(pg_session_factory):
    """Two concurrent consumes of 8 against 10 remaining: one wins, total is 8."""
    sm = pg_session_factory
    async with sm() as db:
        mat = await _seed_material(db, code="PG-STL-OV")
        order = await _confirmed_order(db, "t3@example.com")
        await db.commit()
        po, mr = await _started_production(db, order.id, mat)
        await db.commit()
        po_id, mr_id = po.id, mr.id

    async def consume_eight():
        async with sm() as db:
            try:
                await production_service.consume_material(
                    db,
                    production_order_id=po_id,
                    material_reservation_id=mr_id,
                    quantity=Decimal("8"),
                    idempotency_key=uuid.uuid4(),
                    actor_user_id=None,
                )
                await db.commit()
                return "ok"
            except ValidationFailedError:
                await db.rollback()
                return "ValidationFailedError"
            except Exception as exc:  # surfaced via result string for assertion
                await db.rollback()
                return f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(consume_eight(), consume_eight())
    assert sorted(results) == ["ValidationFailedError", "ok"], results

    async with sm() as db:
        fresh = await db.get(ProductionMaterialReservation, mr_id)
    assert fresh.quantity_consumed == Decimal("8")


@pytest.mark.anyio
async def test_concurrent_duplicate_claims_single_active(pg_session_factory):
    """Two concurrent deposit claims: the partial unique index allows exactly one."""
    sm = pg_session_factory
    async with sm() as db:
        customer = Customer(full_name="PG Claim", email="t4@example.com")
        db.add(customer)
        await db.flush()
        quote = await quotes_service.create_quote(
            db,
            customer_id=customer.id,
            custom_request_id=None,
            lines=[
                quotes_service.QuoteLineInput.build(
                    description="Gadget", quantity=1, unit_label="pcs", unit_price_minor=10000
                )
            ],
            valid_until=datetime.now(UTC) + timedelta(days=7),
        )
        quote = await quotes_service.change_status(db, quote, QuoteStatus.SENT)
        quote = await quotes_service.change_status(db, quote, QuoteStatus.ACCEPTED)
        order = await orders_service.create_from_quote(db, quote)
        config = (await db.execute(select(PaymentConfiguration).limit(1))).scalar_one_or_none()
        if config is None:
            db.add(
                PaymentConfiguration(
                    account_holder="ZARO",
                    account_identifier="CCP-123",
                    default_deposit_percentage=40,
                )
            )
        else:
            await db.execute(update(PaymentConfiguration).values(account_identifier="CCP-123"))
        await db.commit()
        order_id = order.id

    async def claim_once():
        async with sm() as db:
            try:
                fresh_order = await db.get(Order, order_id)
                await payments_service.create_deposit_claim(db, fresh_order, customer_id=None)
                await db.commit()
                return "ok"
            except ConflictError:
                await db.rollback()
                return "ConflictError"
            except Exception as exc:  # surfaced via result string for assertion
                await db.rollback()
                return f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(claim_once(), claim_once())
    assert sorted(results) == ["ConflictError", "ok"], results


async def _order_with_under_review_claim(sm, email: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed an order at PENDING_DEPOSIT with a deposit claim UNDER_REVIEW."""
    async with sm() as db:
        customer = Customer(full_name="PG Lock", email=email)
        db.add(customer)
        await db.flush()
        quote = await quotes_service.create_quote(
            db,
            customer_id=customer.id,
            custom_request_id=None,
            lines=[
                quotes_service.QuoteLineInput.build(
                    description="Lock Widget", quantity=1, unit_label="pcs", unit_price_minor=40000
                )
            ],
            valid_until=datetime.now(UTC) + timedelta(days=7),
        )
        quote = await quotes_service.change_status(db, quote, QuoteStatus.SENT)
        quote = await quotes_service.change_status(db, quote, QuoteStatus.ACCEPTED)
        order = await orders_service.create_from_quote(db, quote)
        config = (await db.execute(select(PaymentConfiguration).limit(1))).scalar_one_or_none()
        if config is None:
            db.add(
                PaymentConfiguration(
                    account_holder="ZARO",
                    account_identifier="CCP-LOCK",
                    default_deposit_percentage=40,
                )
            )
        else:
            await db.execute(update(PaymentConfiguration).values(account_identifier="CCP-LOCK"))
        await db.flush()

        payment = await payments_service.create_deposit_claim(db, order, customer_id=None)
        asset = FileAsset(
            storage_key=f"pg/lock-{uuid.uuid4()}.png",
            content_type="image/png",
            size_bytes=64,
            sha256="a" * 64,
            purpose=FilePurpose.PAYMENT_PROOF,
            visibility=FileVisibility.PRIVATE,
        )
        db.add(asset)
        await db.flush()
        await payments_service.attach_proof(db, payment, asset_id=asset.id)
        await payments_service.submit_for_review(db, payment)
        await db.commit()
        return order.id, payment.id


@pytest.mark.anyio
async def test_concurrent_confirm_and_cancel_no_deadlock(pg_session_factory):
    """confirm (P->O->Q) racing cancel (P->O->Q): one winner, never a 40P01.

    Regression for BL-03: cancel previously locked Order -> Quote -> Payment,
    inverting the (Payment, Order) pair used by confirm_payment and creating a
    textbook PostgreSQL deadlock. Both paths must now use the same global lock
    order (Payment -> Order -> Quote) and serialize cleanly.
    """
    sm = pg_session_factory
    order_id, payment_id = await _order_with_under_review_claim(sm, "bl3@example.com")

    async def confirm():
        async with sm() as db:
            try:
                await payments_service.confirm_payment(db, payment_id, reviewer_user_id=uuid.uuid4())
                await db.commit()
                return "ok"
            except Exception as exc:  # surfaced via result string for assertion
                await db.rollback()
                return f"{type(exc).__name__}: {exc}"

    async def cancel():
        async with sm() as db:
            try:
                await orders_service.cancel_order_with_claim(db, order_id, reason="regression")
                await db.commit()
                return "ok"
            except Exception as exc:  # surfaced via result string for assertion
                await db.rollback()
                return f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(confirm(), cancel())
    lowered = [str(r).lower() for r in results]
    assert not any("deadlock" in r or "40p01" in r for r in lowered), results
    assert sorted(results)[0] == "ok", results
    assert sorted(results)[1].startswith(("InvalidStateTransition", "ConflictError")), results

    async with sm() as db:
        order = await db.get(Order, order_id)
        claim = await db.get(Payment, payment_id)
    assert (str(order.status), str(claim.status)) in (
        ("confirmed", "confirmed"),
        ("cancelled", "cancelled"),
    ), (str(order.status), str(claim.status))
