"""Production service tests: order lifecycle, reservation math, QC gates."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidStateTransition,
    NotFoundError,
    ValidationFailedError,
)
from app.models.enums import (
    ProductionMaterialReservationStatus,
    ProductionOrderStatus,
    QuoteStatus,
    Role,
)
from app.models.material import Material
from app.services import inventory_service, orders_service, production_service, quotes_service


@pytest.fixture
async def actor(db_session, user_factory):
    return await user_factory(role=Role.ADMIN)


@pytest.fixture
async def worker(db_session, user_factory):
    return await user_factory(role=Role.WORKER)


@pytest.fixture
async def material(db_session):
    mat = Material(name="Pine Board", code="PINE-BOARD-001", category="wood", unit="pcs", is_active=True)
    db_session.add(mat)
    await db_session.commit()
    return mat


@pytest.fixture
async def stocked(db_session, material):
    await inventory_service.purchase(
        db_session, material_id=material.id, quantity=Decimal("100"), idempotency_key=uuid.uuid4()
    )
    return material


async def _confirmed_order(db_session, make_customer=None):
    """Build a CONFIRMED order via the real quote -> order -> deposit path."""
    from app.models.customer import Customer

    customer = Customer(full_name="Prod Customer", email="prod-cust@example.com")
    db_session.add(customer)
    await db_session.commit()

    quote = await quotes_service.create_quote(
        db_session,
        customer_id=customer.id,
        custom_request_id=None,
        lines=[
            quotes_service.QuoteLineInput.build(
                description="Chair", quantity=2, unit_label="pcs", unit_price_minor=50000
            ),
        ],
        valid_until=datetime.now(UTC) + timedelta(days=7),
        deposit_percentage=50,
    )
    quote = await quotes_service.change_status(db_session, quote, QuoteStatus.SENT)
    quote = await quotes_service.change_status(db_session, quote, QuoteStatus.ACCEPTED)
    order = await orders_service.create_from_quote(db_session, quote)
    order = await orders_service.apply_confirmed_deposit(db_session, order, amount_minor=order.deposit_required_minor)
    return order


@pytest.fixture
async def confirmed_order(db_session):
    return await _confirmed_order(db_session)


@pytest.fixture
async def production_order(db_session, confirmed_order, actor):
    return await production_service.create_production_order(db_session, order=confirmed_order, created_by=actor.id)


async def _reservations(db_session, production_order_id):
    from sqlalchemy import select

    from app.models.production import ProductionMaterialReservation

    return (
        (
            await db_session.execute(
                select(ProductionMaterialReservation).where(
                    ProductionMaterialReservation.production_order_id == production_order_id
                )
            )
        )
        .scalars()
        .all()
    )


def _requirement(material, qty="10"):
    return production_service.MaterialRequirement(
        material_id=material.id,
        material_name=material.name,
        material_code=material.code,
        material_unit=str(material.unit),
        quantity_required=Decimal(qty),
        unit_price_minor=1000,
    )


class TestCreate:
    async def test_create_from_confirmed_order(self, db_session, production_order, confirmed_order):
        assert production_order.order_id == confirmed_order.id
        assert production_order.production_number.startswith("ZPROD-")
        assert ProductionOrderStatus(production_order.status) == ProductionOrderStatus.PENDING

    async def test_create_rejects_non_confirmed_order(self, db_session):
        from app.models.customer import Customer

        customer = Customer(full_name="C2", email="c2@example.com")
        db_session.add(customer)
        await db_session.commit()
        quote = await quotes_service.create_quote(
            db_session,
            customer_id=customer.id,
            custom_request_id=None,
            lines=[
                quotes_service.QuoteLineInput.build(
                    description="Table", quantity=1, unit_label="pcs", unit_price_minor=10000
                ),
            ],
            valid_until=datetime.now(UTC) + timedelta(days=7),
        )
        quote = await quotes_service.change_status(db_session, quote, QuoteStatus.SENT)
        quote = await quotes_service.change_status(db_session, quote, QuoteStatus.ACCEPTED)
        order = await orders_service.create_from_quote(db_session, quote)
        with pytest.raises(InvalidStateTransition):
            await production_service.create_production_order(db_session, order=order)

    async def test_create_twice_conflicts(self, db_session, production_order):
        from app.models.order import Order

        order = await db_session.get(Order, production_order.order_id)
        with pytest.raises(ConflictError):
            await production_service.create_production_order(db_session, order=order)


class TestPlanAndReserve:
    async def test_plan_snapshots_material_details(self, db_session, production_order, stocked):
        po = await production_service.plan_production(
            db_session, production_order_id=production_order.id, requirements=[_requirement(stocked)]
        )
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.PLANNED
        reservations = await _reservations(db_session, po.id)
        assert len(reservations) == 1
        mr = reservations[0]
        assert mr.material_name == "Pine Board"
        assert mr.material_code == "PINE-BOARD-001"
        assert mr.quantity_required == Decimal("10")

    async def test_plan_twice_rejected(self, db_session, production_order, stocked):
        await production_service.plan_production(
            db_session, production_order_id=production_order.id, requirements=[_requirement(stocked)]
        )
        with pytest.raises(InvalidStateTransition):
            await production_service.plan_production(
                db_session, production_order_id=production_order.id, requirements=[_requirement(stocked)]
            )

    async def test_plan_requires_unknown_material_rejected(self, db_session, production_order):
        with pytest.raises(NotFoundError):
            await production_service.plan_production(
                db_session,
                production_order_id=production_order.id,
                requirements=[
                    production_service.MaterialRequirement(
                        material_id=uuid.uuid4(),
                        material_name="Ghost",
                        material_code="GHOST",
                        material_unit="pcs",
                        quantity_required=Decimal("1"),
                        unit_price_minor=100,
                    )
                ],
            )

    async def test_reserve_moves_stock_to_reserved(self, db_session, production_order, stocked):
        await production_service.plan_production(
            db_session, production_order_id=production_order.id, requirements=[_requirement(stocked)]
        )
        po = await production_service.reserve_materials(db_session, production_order.id)
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.MATERIALS_RESERVED
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        assert level.on_hand == Decimal("100")
        assert level.reserved == Decimal("10")

    async def test_reserve_insufficient_stock_leaves_nothing_reserved(self, db_session, production_order, stocked):
        await production_service.plan_production(
            db_session,
            production_order_id=production_order.id,
            requirements=[_requirement(stocked, "1000")],
        )
        with pytest.raises(ValidationFailedError):
            await production_service.reserve_materials(db_session, production_order.id)
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        assert level.reserved == Decimal("0")
        reservations = await _reservations(db_session, production_order.id)
        assert (
            ProductionMaterialReservationStatus(reservations[0].status) == ProductionMaterialReservationStatus.PENDING
        )


@pytest.fixture
async def reserved_setup(db_session, production_order, stocked):
    po = await production_service.plan_production(
        db_session, production_order_id=production_order.id, requirements=[_requirement(stocked)]
    )
    po = await production_service.reserve_materials(db_session, po.id)
    reservations = await _reservations(db_session, po.id)
    return po, reservations[0]


class TestStartPauseResume:
    async def test_start_requires_reserved(self, db_session, production_order, stocked):
        await production_service.plan_production(
            db_session, production_order_id=production_order.id, requirements=[_requirement(stocked)]
        )
        with pytest.raises(InvalidStateTransition):
            await production_service.start_production(db_session, production_order.id)

    async def test_start_pause_resume_cycle(self, db_session, reserved_setup):
        po, _ = reserved_setup
        po = await production_service.start_production(db_session, po.id)
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.IN_PRODUCTION
        po = await production_service.pause_production(db_session, po.id)
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.PAUSED
        po = await production_service.resume_production(db_session, po.id)
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.IN_PRODUCTION


@pytest.fixture
async def in_production(db_session, reserved_setup):
    po, _mr = reserved_setup
    po = await production_service.start_production(db_session, po.id)
    reservations = await _reservations(db_session, po.id)
    return po, reservations[0]


class TestConsumeWasteReturnRelease:
    async def test_consume_reduces_stock_and_reservation(self, db_session, in_production, stocked, actor):
        po, mr = in_production
        mr = await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("4"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        assert mr.quantity_consumed == Decimal("4")
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        assert level.on_hand == Decimal("96")
        assert level.reserved == Decimal("6")

    async def test_consume_beyond_remaining_rejected(self, db_session, in_production, actor):
        po, mr = in_production
        with pytest.raises(ValidationFailedError):
            await production_service.consume_material(
                db_session,
                production_order_id=po.id,
                material_reservation_id=mr.id,
                quantity=Decimal("11"),
                idempotency_key=uuid.uuid4(),
                actor_user_id=actor.id,
            )

    async def test_consume_idempotent_retry_does_not_double_count(self, db_session, in_production, stocked, actor):
        po, mr = in_production
        key = uuid.uuid4()
        first = await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("4"),
            idempotency_key=key,
            actor_user_id=actor.id,
        )
        assert first.quantity_consumed == Decimal("4")
        second = await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("4"),
            idempotency_key=key,
            actor_user_id=actor.id,
        )
        assert second.quantity_consumed == Decimal("4")
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        assert level.on_hand == Decimal("96")
        assert level.reserved == Decimal("6")

    async def test_retry_after_terminal_transition_still_replays(self, db_session, in_production, stocked, actor):
        """Full consume moves the reservation to CONSUMED; retrying the same
        key must still replay successfully (replay precedes state gates)."""
        from app.models.enums import ProductionMaterialReservationStatus as ResStatus

        po, mr = in_production
        key = uuid.uuid4()
        first = await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("10"),
            idempotency_key=key,
            actor_user_id=actor.id,
        )
        assert ResStatus(first.status) == ResStatus.CONSUMED
        second = await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("10"),
            idempotency_key=key,
            actor_user_id=actor.id,
        )
        assert second.quantity_consumed == Decimal("10")
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        assert level.on_hand == Decimal("90")
        assert level.reserved == Decimal("0")

    async def test_release_beyond_remaining_rejected_after_partial_consume(self, db_session, in_production, actor):
        po, mr = in_production
        await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("7"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        with pytest.raises(ValidationFailedError):
            await production_service.return_material(
                db_session,
                production_order_id=po.id,
                material_reservation_id=mr.id,
                quantity=Decimal("4"),
                idempotency_key=uuid.uuid4(),
                actor_user_id=actor.id,
            )

    async def test_return_restores_availability(self, db_session, in_production, stocked, actor):
        po, mr = in_production
        mr = await production_service.return_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("3"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        assert mr.quantity_returned == Decimal("3")
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        assert level.on_hand == Decimal("100")
        assert level.reserved == Decimal("7")


class TestQualityCheck:
    @pytest.fixture
    async def qc_ready(self, db_session, in_production, actor):
        """IN_PRODUCTION order with all materials consumed (QC may start)."""
        po, mr = in_production
        await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("10"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        return po

    async def test_start_requires_materials_accounted(self, db_session, in_production, actor):
        po, _ = in_production
        with pytest.raises(ValidationFailedError):
            await production_service.start_quality_check(db_session, po.id, inspector_id=actor.id)

    async def test_inspector_cannot_be_assigned_worker(self, db_session, qc_ready, worker):
        qc_ready.assigned_worker_id = worker.id
        await db_session.commit()
        with pytest.raises(ForbiddenError):
            await production_service.start_quality_check(db_session, qc_ready.id, inspector_id=worker.id)

    async def test_approve_moves_to_ready(self, db_session, qc_ready, actor):
        await production_service.start_quality_check(db_session, qc_ready.id, inspector_id=actor.id)
        po = await production_service.complete_quality_check(
            db_session, qc_ready.id, approved=True, inspector_id=actor.id, notes="good"
        )
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.READY

    async def test_second_decision_rejected(self, db_session, qc_ready, actor, worker):
        await production_service.start_quality_check(db_session, qc_ready.id, inspector_id=actor.id)
        await production_service.complete_quality_check(db_session, qc_ready.id, approved=True, inspector_id=actor.id)
        with pytest.raises(InvalidStateTransition):
            await production_service.complete_quality_check(
                db_session, qc_ready.id, approved=False, inspector_id=worker.id
            )

    async def test_reject_returns_order_to_production(self, db_session, qc_ready, actor):
        await production_service.start_quality_check(db_session, qc_ready.id, inspector_id=actor.id)
        po = await production_service.complete_quality_check(
            db_session, qc_ready.id, approved=False, inspector_id=actor.id, notes="rework"
        )
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.IN_PRODUCTION


class TestComplete:
    @pytest.fixture
    async def ready_order(self, db_session, in_production, actor):
        po, mr = in_production
        await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("10"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        await production_service.start_quality_check(db_session, po.id, inspector_id=actor.id)
        return await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=actor.id)

    async def test_complete_requires_ready(self, db_session, in_production):
        po, _ = in_production
        with pytest.raises(InvalidStateTransition):
            await production_service.complete_production(db_session, po.id)

    async def test_complete_after_approval(self, db_session, ready_order):
        assert ProductionOrderStatus(ready_order.status) == ProductionOrderStatus.READY
        po = await production_service.complete_production(db_session, ready_order.id)
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.COMPLETED


class TestCancel:
    async def test_cancel_releases_only_the_remainder(self, db_session, in_production, stocked, actor):
        po, mr = in_production
        await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("4"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        po = await production_service.cancel_production(db_session, po.id, reason="customer cancelled")
        assert ProductionOrderStatus(po.status) == ProductionOrderStatus.CANCELLED
        level = await inventory_service.get_stock_level(db_session, stocked.id)
        # 4 consumed stays consumed; the other 6 go back to available.
        assert level.on_hand == Decimal("96")
        assert level.reserved == Decimal("0")

    async def test_cancel_completed_order_rejected(self, db_session, in_production, actor):
        po, mr = in_production
        await production_service.consume_material(
            db_session,
            production_order_id=po.id,
            material_reservation_id=mr.id,
            quantity=Decimal("10"),
            idempotency_key=uuid.uuid4(),
            actor_user_id=actor.id,
        )
        await production_service.start_quality_check(db_session, po.id, inspector_id=actor.id)
        await production_service.complete_quality_check(db_session, po.id, approved=True, inspector_id=actor.id)
        await production_service.complete_production(db_session, po.id)
        with pytest.raises(InvalidStateTransition):
            await production_service.cancel_production(db_session, po.id, reason="test")

    async def test_cancel_twice_rejected(self, db_session, in_production):
        po, _ = in_production
        await production_service.cancel_production(db_session, po.id, reason="test")
        with pytest.raises(InvalidStateTransition):
            await production_service.cancel_production(db_session, po.id, reason="test")
