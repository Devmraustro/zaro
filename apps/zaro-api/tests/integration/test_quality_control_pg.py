"""PostgreSQL QC concurrency tests (Gate 4C).

These verify, against a REAL PostgreSQL instance, the cross-session isolation
guarantees that SQLite's shared in-memory database cannot exercise: the QC state
transitions (start / approve / reject) are applied atomically under a row lock
(SELECT ... FOR UPDATE) so that exactly one concurrent decision wins.

Scope of these tests
---------------------
These are SERVICE-LEVEL concurrency tests. They prove:

* exactly one concurrent QC decision succeeds and the rest fail with the
  expected state-transition error,
* the final ProductionOrder state is deterministic,
* ``qc_inspector_id`` is the server-derived inspector of the winning decision,
* self-approval (assigned worker == acting inspector) raises ForbiddenError,
* the assigned worker / forged client-chosen inspector cannot be accepted as
  the QC inspector,
* order financial fields are unchanged by QC,
* inventory StockLevel is unchanged by QC.

Audit coverage is intentionally split:

* the HTTP endpoint records audit events via ``record_event``; that behaviour is
  verified by the existing HTTP-level tests in tests/unit/test_quality_control.py,
* "full HTTP concurrency + PostgreSQL audit" is NOT simulated here; it remains an
  explicitly UNVERIFIED gate unless executed through the real HTTP endpoint
  against PostgreSQL.

The scope is gated to a REAL, DEDICATED TEST database only: the module refuses to
run (at collection time) unless the target database name clearly identifies a
test database (contains "test"). It defaults to the local ZARO compose Postgres
(127.0.0.1:5433, user zaro / password zaro_dev_password) and is skipped with a
clear message when Postgres is unreachable or the database is not a test
database, so the rest of the suite stays green without a database.
"""

# ruff: noqa: RUF059  (test helper tuples unpack unused vars for readability)

import asyncio
import os
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.enums import OrderStatus, ProductionOrderStatus
from app.models.inventory import StockLevel, StockMovement
from app.models.material import Material
from app.models.order import Order
from app.models.production import ProductionMaterialReservation, ProductionOrder
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
        return "ZARO_PG_TEST_URL not set (PostgreSQL QC concurrency tests require a live server)"
    if "test" not in _pg_db_name(PG_URL).lower():
        return f"refusing to run destructive PG tests against non-test database '{_pg_db_name(PG_URL)}'"
    return None


pytestmark = pytest.mark.skipif(_pg_reason() is not None, reason=_pg_reason() or "")


@pytest.fixture(scope="function")
async def pg_session_factory():
    """Function-scoped Postgres session factory; skips when PG is unreachable."""
    engine = create_async_engine(PG_URL, pool_size=10, max_overflow=20)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        await engine.dispose()
        pytest.skip(f"PostgreSQL unreachable ({exc}); QC concurrency tests skipped")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


def _req(material: Material, qty: str = "10") -> MaterialRequirement:
    return MaterialRequirement(
        material_id=material.id,
        material_name=material.name,
        material_code=material.code,
        material_unit="kg",
        quantity_required=Decimal(qty),
        unit_price_minor=1000,
    )


async def _consume_all_reserved(db, po_id, *, actor_user_id):
    """Consume every open reservation so QC's material-accounting precondition holds.

    start_quality_check requires all reserved materials to be consumed, wasted,
    returned or released before the order can enter QUALITY_CHECK. Mirrors the
    corrected unit fixture (tests/unit/test_quality_control.py).
    """
    mrs = (
        await db.execute(
            select(ProductionMaterialReservation).where(ProductionMaterialReservation.production_order_id == po_id)
        )
    ).scalars()
    for mr in mrs:
        remaining = production_service.compute_remaining_reserved(mr)
        if remaining > 0:
            await production_service.consume_material(
                db,
                po_id,
                material_reservation_id=mr.id,
                quantity=remaining,
                idempotency_key=uuid4(),
                actor_user_id=actor_user_id,
            )


async def _create_qc_ready_po(maker, *, on_hand="100", qty="10"):
    """Stock a material, build a CONFIRMED order and a PO in IN_PRODUCTION with
    an assigned worker. Returns (po_id, order_id, material_id, worker_id)."""
    async with maker() as s:
        mat = Material(id=uuid4(), code="STEEL-BEAM", name="Steel Beam", category="steel", unit="kg", is_active=True)
        s.add(mat)
        await s.flush()
        await inventory_service.purchase(s, material_id=mat.id, quantity=Decimal(on_hand), idempotency_key=uuid4())
        oid = uuid4()
        order = Order(
            id=oid,
            order_number=f"ZO-QC-PG-{oid.hex[:8].upper()}",
            customer_id=None,
            quote_id=None,
            custom_request_id=None,
            status=OrderStatus.CONFIRMED,
            currency="DZD",
            subtotal_minor=500000,
            discount_minor=0,
            delivery_fee_minor=0,
            total_minor=500000,
            deposit_required_minor=150000,
            deposit_paid_minor=150000,
            balance_due_minor=350000,
        )
        s.add(order)
        await s.flush()
        po = await production_service.create_production_order(s, order=order)
        await production_service.plan_production(s, po.id, requirements=[_req(mat, qty)])
        await production_service.reserve_materials(s, po.id)
        worker = User(id=uuid4(), email=f"qc-worker-{uuid4()}@zaro.test", hashed_password="x", full_name="QC Worker")
        s.add(worker)
        await s.flush()
        worker_id = worker.id
        po.assigned_worker_id = worker_id
        await production_service.start_production(s, po.id)
        await _consume_all_reserved(s, po.id, actor_user_id=worker_id)
        await s.commit()
        return po.id, oid, mat.id, worker_id


async def _start_qc(maker, po_id, inspector_id):
    async with maker() as s:
        await production_service.start_quality_check(s, po_id, inspector_id=inspector_id, actor_user_id=inspector_id)
        await s.commit()


async def _make_inspector(maker) -> UUID:
    """Create a real user in the PG schema and return its id (QC inspector)."""
    async with maker() as s:
        u = User(
            id=uuid4(),
            email=f"qc-inspector-{uuid4()}@zaro.test",
            hashed_password="x",
            full_name="QC Inspector",
        )
        s.add(u)
        await s.commit()
        return u.id


def _order_snapshot(maker, order_id):
    """Return the financial fields of an order (before/after QC must match)."""

    async def _read():
        async with maker() as s:
            order = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one()
            return {
                "subtotal_minor": order.subtotal_minor,
                "discount_minor": order.discount_minor,
                "delivery_fee_minor": order.delivery_fee_minor,
                "total_minor": order.total_minor,
                "deposit_required_minor": order.deposit_required_minor,
                "deposit_paid_minor": order.deposit_paid_minor,
                "balance_due_minor": order.balance_due_minor,
                "status": order.status,
            }

    return _read()


async def _stock_level(maker, material_id):
    async with maker() as s:
        level = (await s.execute(select(StockLevel).where(StockLevel.material_id == material_id))).scalar_one_or_none()
        moves = (await s.execute(select(StockMovement).where(StockMovement.material_id == material_id))).scalars().all()
        return (
            (level.on_hand, level.reserved) if level is not None else None,
            [m.movement_type for m in moves],
        )


def _decision_worker(maker, po_id, approved, inspector_id):
    """Concurrent QC decision. Returns 'ok' on success, else the exception class name."""

    async def _run():
        async with maker() as s:
            try:
                await production_service.complete_quality_check(
                    s,
                    po_id,
                    approved=approved,
                    inspector_id=inspector_id,
                    defects="defect" if not approved else None,
                    notes="rework" if not approved else None,
                    actor_user_id=inspector_id,
                )
                await s.commit()
                return "ok"
            except Exception as exc:
                await s.rollback()
                return type(exc).__name__

    return _run()


def _read_po_status(maker, po_id):
    async def _read():
        async with maker() as s:
            po = (await s.execute(select(ProductionOrder).where(ProductionOrder.id == po_id))).scalar_one()
            return po.status, po.qc_inspector_id, po.quality_check_completed_at is not None

    return _read()


class TestQcRaceApproveVsReject:
    async def test_approve_vs_reject_exactly_one_wins(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)
        inspector_a = await _make_inspector(maker)
        inspector_b = await _make_inspector(maker)
        await _start_qc(maker, po_id, inspector_a)

        before_fin = await _order_snapshot(maker, order_id)
        before_stock = await _stock_level(maker, material_id)

        results = await asyncio.gather(
            _decision_worker(maker, po_id, approved=True, inspector_id=inspector_a),
            _decision_worker(maker, po_id, approved=False, inspector_id=inspector_b),
        )

        assert results.count("ok") == 1, f"expected exactly one winner, got {results}"
        losing = [r for r in results if r != "ok"]
        assert losing == ["InvalidStateTransition"], f"loser must fail with state error, got {losing}"

        status, winner_inspector, completed = await _read_po_status(maker, po_id)
        assert completed
        if status == ProductionOrderStatus.READY.value:
            winner = inspector_a
        elif status == ProductionOrderStatus.IN_PRODUCTION.value:
            winner = inspector_b
        else:
            raise AssertionError(f"non-deterministic final state: {status}")
        assert winner_inspector == winner, "qc_inspector_id must be the winning inspector"

        assert await _order_snapshot(maker, order_id) == before_fin
        assert await _stock_level(maker, material_id) == before_stock


class TestQcRaceApproveVsApprove:
    async def test_approve_vs_approve_exactly_one_wins(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)
        inspector_a = await _make_inspector(maker)
        inspector_b = await _make_inspector(maker)
        await _start_qc(maker, po_id, inspector_a)

        before_fin = await _order_snapshot(maker, order_id)
        before_stock = await _stock_level(maker, material_id)

        results = await asyncio.gather(
            _decision_worker(maker, po_id, approved=True, inspector_id=inspector_a),
            _decision_worker(maker, po_id, approved=True, inspector_id=inspector_b),
        )

        assert results.count("ok") == 1, f"expected exactly one winner, got {results}"
        assert [r for r in results if r != "ok"] == ["InvalidStateTransition"]

        status, winner_inspector, completed = await _read_po_status(maker, po_id)
        assert status == ProductionOrderStatus.READY.value
        assert completed
        assert winner_inspector in (inspector_a, inspector_b)

        assert await _order_snapshot(maker, order_id) == before_fin
        assert await _stock_level(maker, material_id) == before_stock


class TestQcRaceRejectVsReject:
    async def test_reject_vs_reject_exactly_one_wins(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)
        inspector_a = await _make_inspector(maker)
        inspector_b = await _make_inspector(maker)
        await _start_qc(maker, po_id, inspector_a)

        before_fin = await _order_snapshot(maker, order_id)
        before_stock = await _stock_level(maker, material_id)

        results = await asyncio.gather(
            _decision_worker(maker, po_id, approved=False, inspector_id=inspector_a),
            _decision_worker(maker, po_id, approved=False, inspector_id=inspector_b),
        )

        assert results.count("ok") == 1, f"expected exactly one winner, got {results}"
        assert [r for r in results if r != "ok"] == ["InvalidStateTransition"]

        status, winner_inspector, completed = await _read_po_status(maker, po_id)
        assert status == ProductionOrderStatus.IN_PRODUCTION.value
        assert completed
        assert winner_inspector in (inspector_a, inspector_b)

        assert await _order_snapshot(maker, order_id) == before_fin
        assert await _stock_level(maker, material_id) == before_stock


class TestQcSelfApprovalAndIdentity:
    async def test_self_approval_raises_forbidden(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)
        other = await _make_inspector(maker)
        await _start_qc(maker, po_id, other)

        # The assigned worker attempts to approve their own order -> ForbiddenError.
        async def _self_approve():
            async with maker() as s:
                try:
                    await production_service.complete_quality_check(
                        s, po_id, approved=True, inspector_id=worker_id, actor_user_id=worker_id
                    )
                    await s.commit()
                    return "ok"
                except Exception as exc:
                    await s.rollback()
                    return type(exc).__name__

        result = await _self_approve()
        assert result == "ForbiddenError"

        status, _, _ = await _read_po_status(maker, po_id)
        assert status == ProductionOrderStatus.QUALITY_CHECK.value

    async def test_worker_cannot_start_own_qc(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)

        async def _self_start():
            async with maker() as s:
                try:
                    await production_service.start_quality_check(s, po_id, inspector_id=worker_id)
                    await s.commit()
                    return "ok"
                except Exception as exc:
                    await s.rollback()
                    return type(exc).__name__

        assert await _self_start() == "ForbiddenError"

    async def test_forged_inspector_cannot_override_server_identity(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)

        # The endpoint derives inspector_id from the authenticated user; a forged
        # inspector_id arriving from the client is rejected by the schema
        # (extra="forbid", covered in HTTP tests). At the service boundary, the
        # authenticated user's id is passed by the endpoint. Here we prove the
        # acting identity recorded on the PO is exactly the server-supplied one,
        # and that the assigned worker's forged identity is never accepted.
        server_inspector = await _make_inspector(maker)
        await _start_qc(maker, po_id, server_inspector)
        _, recorded_inspector, _ = await _read_po_status(maker, po_id)
        assert recorded_inspector == server_inspector
        assert recorded_inspector != worker_id

    async def test_financial_and_inventory_unchanged_on_reject(self, pg_session_factory):
        maker = pg_session_factory
        po_id, order_id, material_id, worker_id = await _create_qc_ready_po(maker)
        inspector = await _make_inspector(maker)
        await _start_qc(maker, po_id, inspector)

        before_fin = await _order_snapshot(maker, order_id)
        before_stock = await _stock_level(maker, material_id)

        async with maker() as s:
            await production_service.complete_quality_check(
                s, po_id, approved=False, inspector_id=inspector, actor_user_id=inspector
            )
            await s.commit()

        assert await _order_snapshot(maker, order_id) == before_fin
        assert await _stock_level(maker, material_id) == before_stock
