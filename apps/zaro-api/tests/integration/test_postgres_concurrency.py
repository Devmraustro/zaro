"""PostgreSQL concurrency tests for the production/inventory domain (Gate 4B).

These verify cross-session isolation guarantees that SQLite's shared in-memory
database cannot exercise: row-locked reservation races, idempotency under
concurrency, and stock invariants under load.

Requires a reachable PostgreSQL instance. The scope is gated to a REAL, DEDICATED
TEST database only: the module refuses to run (at collection time) unless the
target database name clearly identifies a test database (contains "test"). It
defaults to the local ZARO compose Postgres (127.0.0.1:5433, user zaro / password
zaro_dev_password) and is skipped with a clear message when Postgres is
unreachable or the database is not a test database, so the rest of the suite
stays green without a database.
"""

import asyncio
import os
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.enums import OrderStatus
from app.models.inventory import StockLevel, StockMovement
from app.models.material import Material
from app.models.order import Order
from app.models.production import ProductionMaterialReservation
from app.models.user import User
from app.services import inventory_service, production_service
from app.services.production_service import MaterialRequirement

PG_URL = os.environ.get("ZARO_PG_TEST_URL", "postgresql+asyncpg://zaro:zaro_dev_password@127.0.0.1:5433/zaro")


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
        return "ZARO_PG_TEST_URL not set (PostgreSQL concurrency tests require a live server)"
    if "test" not in _pg_db_name(PG_URL).lower():
        return f"refusing to run destructive PG tests against non-test database '{_pg_db_name(PG_URL)}'"
    return None


pytestmark = pytest.mark.skipif(_pg_reason() is not None, reason=_pg_reason() or "")


@pytest.fixture(scope="function")
async def pg_session_factory():
    """Function-scoped Postgres session factory; skips when PG is unreachable.

    A fresh engine is created per test because asyncpg connections are bound to
    the asyncio loop that created them, and pytest (asyncio_mode=auto) runs each
    test on its own loop. All concurrent workers within a single test share the
    same loop, so this matches the module's telemetry isolation guarantees.
    """
    engine = create_async_engine(PG_URL, pool_size=10, max_overflow=20)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        await engine.dispose()
        pytest.skip(f"PostgreSQL unreachable ({exc}); concurrency tests skipped")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _create_material_and_stock(maker, *, code="STEEL-BEAM", qty="100"):
    async with maker() as s:
        mat = Material(id=uuid4(), code=code, name="Steel Beam", category="steel", unit="kg", is_active=True)
        s.add(mat)
        await s.flush()
        if Decimal(qty) > 0:  # purchase (stock) only when qty > 0; qty=0 means no initial stock
            await inventory_service.purchase(s, material_id=mat.id, quantity=Decimal(qty), idempotency_key=uuid4())
        worker = User(
            id=uuid4(), email=f"conc-worker-{uuid4()}@zaro.test", hashed_password="x", full_name="Conc Worker"
        )
        s.add(worker)
        await s.flush()
        await s.commit()
        return mat.id, worker.id


async def _create_planned_po(maker, material_id, qty="60"):
    async with maker() as s:
        oid = uuid4()
        order = Order(
            id=oid,
            order_number=f"ZO-CONC-{oid.hex[:8].upper()}",
            customer_id=None,
            quote_id=None,
            custom_request_id=None,
            status=OrderStatus.CONFIRMED,
            currency="DZD",
            subtotal_minor=100000,
            discount_minor=0,
            delivery_fee_minor=0,
            total_minor=100000,
            deposit_required_minor=30000,
            deposit_paid_minor=0,
            balance_due_minor=100000,
        )
        s.add(order)
        await s.flush()
        po = await production_service.create_production_order(s, order=order)
        req = MaterialRequirement(
            material_id=material_id,
            material_name="Steel Beam",
            material_code="STEEL-BEAM",
            material_unit="kg",
            quantity_required=Decimal(qty),
            unit_price_minor=100,
        )
        await production_service.plan_production(s, po.id, requirements=[req])
        await s.commit()
        return po.id


def _reserve_worker(maker, po_id):
    async def _run():
        async with maker() as s:
            try:
                await production_service.reserve_materials(s, po_id)
                await s.commit()
                return "ok"
            except Exception as exc:
                await s.rollback()
                return type(exc).__name__

    return _run()


async def test_concurrent_reserve_no_over_reservation(pg_session_factory):
    """Two POs race for the same material: exactly one may reserve; never over-reserve."""
    maker = pg_session_factory
    material_id, _ = await _create_material_and_stock(maker, qty="100")
    po1 = await _create_planned_po(maker, material_id, qty="60")
    po2 = await _create_planned_po(maker, material_id, qty="60")

    results = await asyncio.gather(_reserve_worker(maker, po1), _reserve_worker(maker, po2))

    assert results.count("ok") == 1, f"expected exactly one successful reservation, got {results}"
    assert any(r == "ValidationFailedError" for r in results)

    async with maker() as s:
        level = (await s.execute(select(StockLevel).where(StockLevel.material_id == material_id))).scalar_one()
        assert level.reserved == Decimal("60")
        assert level.reserved <= level.on_hand  # invariant holds
        count = (await s.execute(select(StockMovement).where(StockMovement.material_id == material_id))).scalars()
        reserve_moves = [m for m in count if m.movement_type == "reserve"]
        assert len(reserve_moves) == 1


async def test_concurrent_idempotent_purchase_single_application(pg_session_factory):
    """Many concurrent purchases with the same idempotency key apply stock once."""
    maker = pg_session_factory
    material_id, _ = await _create_material_and_stock(maker, qty="0")

    key = uuid4()

    async def _purchase():
        async with maker() as s:
            try:
                await inventory_service.purchase(
                    s, material_id=material_id, quantity=Decimal("10"), idempotency_key=key
                )
                await s.commit()
                return "ok"
            except Exception as exc:
                await s.rollback()
                return type(exc).__name__

    results = await asyncio.gather(*[_purchase() for _ in range(5)])

    async with maker() as s:
        level = (await s.execute(select(StockLevel).where(StockLevel.material_id == material_id))).scalar_one()
        assert level.on_hand == Decimal("10"), f"stock applied more than once: {level.on_hand}"
        moves = (await s.execute(select(StockMovement).where(StockMovement.material_id == material_id))).scalars().all()
        assert len(moves) == 1
        assert results.count("ok") == 1


async def test_concurrent_consume_respects_reserved_bound(pg_session_factory):
    """Concurrent consumption never exceeds the reserved amount (CHECK enforced)."""
    maker = pg_session_factory
    material_id, worker_id = await _create_material_and_stock(maker, qty="100")
    po = await _create_planned_po(maker, material_id, qty="10")

    async with maker() as s:
        await production_service.reserve_materials(s, po)
        await production_service.start_production(s, po)
        mr = (
            (
                await s.execute(
                    select(ProductionMaterialReservation).where(ProductionMaterialReservation.production_order_id == po)
                )
            )
            .scalars()
            .one()
        )
        mr_id = mr.id
        await s.commit()

    async def _consume(qty):
        async with maker() as s:
            try:
                await production_service.consume_material(
                    s,
                    po,
                    material_reservation_id=mr_id,
                    quantity=Decimal(qty),
                    idempotency_key=uuid4(),
                    actor_user_id=worker_id,
                )
                await s.commit()
                return "ok"
            except Exception as exc:
                await s.rollback()
                return f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(*[_consume("4"), _consume("4"), _consume("4")])
    assert len(results) == 3
    assert any(r == "ok" for r in results)

    async with maker() as s:
        mr = (
            await s.execute(select(ProductionMaterialReservation).where(ProductionMaterialReservation.id == mr_id))
        ).scalar_one()
        level = (await s.execute(select(StockLevel).where(StockLevel.material_id == material_id))).scalar_one()
        # Invariants must hold under concurrency.
        assert mr.quantity_consumed <= mr.quantity_reserved
        assert level.reserved >= 0
        assert level.on_hand == Decimal("100") - mr.quantity_consumed
        # Each successful consume applies exactly 4; the rest are rejected (never
        # over-consumed beyond the reserved bound of 10).
        assert Decimal("4") * Decimal(str(results.count("ok"))) == mr.quantity_consumed, (
            f"consumed counter drifted from successes: {mr.quantity_consumed}, results={results}"
        )
        assert mr.quantity_consumed <= Decimal("10")
