"""Inventory service tests: balances, invariants, idempotency.

Every stock mutation flows through InventoryService; these tests pin the
delta vectors, the guard invariants (no negative balances, reserved never
above on_hand) and the idempotency contract.
"""

import uuid
from decimal import Decimal

import pytest

from app.core.exceptions import ConflictError, ValidationFailedError
from app.models.enums import Role
from app.models.material import Material
from app.services import inventory_service


@pytest.fixture
async def material(db_session):
    mat = Material(name="Steel Tube", code="STL-TUBE-001", category="steel", unit="kg", is_active=True)
    db_session.add(mat)
    await db_session.commit()
    return mat


@pytest.fixture
async def actor(db_session, user_factory):
    return await user_factory(role=Role.ADMIN)


class TestPurchase:
    async def test_purchase_creates_level_and_movement(self, db_session, material, actor):
        result = await inventory_service.purchase(
            db_session,
            material_id=material.id,
            quantity=Decimal("10"),
            idempotency_key=uuid.uuid4(),
            unit_price_minor=5000,
            actor_user_id=actor.id,
        )
        assert result.stock_level.on_hand == Decimal("10")
        assert result.stock_level.reserved == Decimal("0")
        assert result.previous_on_hand == Decimal("0")
        assert result.movement.quantity == Decimal("10")

    async def test_purchase_accumulates(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        result = await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("5"), idempotency_key=uuid.uuid4()
        )
        assert result.stock_level.on_hand == Decimal("15")


class TestReserveReleaseConsume:
    async def test_reserve_earmarks_without_touching_on_hand(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        ref = uuid.uuid4()
        result = await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        assert result.stock_level.on_hand == Decimal("10")
        assert result.stock_level.reserved == Decimal("6")

    async def test_reserve_beyond_available_is_rejected(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        with pytest.raises(ValidationFailedError):
            await inventory_service.reserve(
                db_session,
                material_id=material.id,
                quantity=Decimal("11"),
                idempotency_key=uuid.uuid4(),
                reference_type="production_order",
                reference_id=uuid.uuid4(),
            )

    async def test_release_returns_to_available(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        ref = uuid.uuid4()
        await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        result = await inventory_service.release(
            db_session,
            material_id=material.id,
            quantity=Decimal("2"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        assert result.stock_level.on_hand == Decimal("10")
        assert result.stock_level.reserved == Decimal("4")

    async def test_release_beyond_reserved_is_rejected(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        with pytest.raises(ValidationFailedError):
            await inventory_service.release(
                db_session,
                material_id=material.id,
                quantity=Decimal("1"),
                idempotency_key=uuid.uuid4(),
                reference_type="production_order",
                reference_id=uuid.uuid4(),
            )

    async def test_consume_reduces_both(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        ref = uuid.uuid4()
        await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        result = await inventory_service.consume(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        assert result.stock_level.on_hand == Decimal("4")
        assert result.stock_level.reserved == Decimal("0")


class TestReturn:
    async def test_return_does_not_mint_stock(self, db_session, material):
        """Regression: RETURN must only decrement reserved (on_hand untouched).

        A (+1, -1) vector here used to create phantom stock on every return.
        """
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        ref = uuid.uuid4()
        await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        result = await inventory_service.return_material(
            db_session,
            material_id=material.id,
            quantity=Decimal("2"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        assert result.stock_level.on_hand == Decimal("10")
        assert result.stock_level.reserved == Decimal("4")

    async def test_return_full_reservation_restores_availability(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        ref = uuid.uuid4()
        await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        result = await inventory_service.return_material(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        assert result.stock_level.on_hand == Decimal("10")
        assert result.stock_level.reserved == Decimal("0")
        assert result.stock_level.available() == Decimal("10")


class TestWasteAndAdjust:
    async def test_production_waste_reduces_both(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        ref = uuid.uuid4()
        await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("6"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        result = await inventory_service.production_waste(
            db_session,
            material_id=material.id,
            quantity=Decimal("1"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=ref,
        )
        assert result.stock_level.on_hand == Decimal("9")
        assert result.stock_level.reserved == Decimal("5")

    async def test_inventory_waste_reduces_on_hand_only(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        result = await inventory_service.inventory_waste(
            db_session,
            material_id=material.id,
            quantity=Decimal("3"),
            idempotency_key=uuid.uuid4(),
        )
        assert result.stock_level.on_hand == Decimal("7")
        assert result.stock_level.reserved == Decimal("0")

    async def test_inventory_waste_cannot_drive_negative(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("2"), idempotency_key=uuid.uuid4()
        )
        with pytest.raises(ValidationFailedError):
            await inventory_service.inventory_waste(
                db_session,
                material_id=material.id,
                quantity=Decimal("3"),
                idempotency_key=uuid.uuid4(),
            )

    async def test_adjust_up_and_down(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        up = await inventory_service.adjust(
            db_session, material_id=material.id, quantity=Decimal("2"), idempotency_key=uuid.uuid4()
        )
        assert up.stock_level.on_hand == Decimal("12")
        down = await inventory_service.adjust(
            db_session, material_id=material.id, quantity=Decimal("-5"), idempotency_key=uuid.uuid4()
        )
        assert down.stock_level.on_hand == Decimal("7")

    async def test_adjust_below_zero_is_rejected(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("2"), idempotency_key=uuid.uuid4()
        )
        with pytest.raises(ValidationFailedError):
            await inventory_service.adjust(
                db_session, material_id=material.id, quantity=Decimal("-3"), idempotency_key=uuid.uuid4()
            )

    async def test_adjust_below_reserved_is_rejected(self, db_session, material):
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=uuid.uuid4()
        )
        await inventory_service.reserve(
            db_session,
            material_id=material.id,
            quantity=Decimal("8"),
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=uuid.uuid4(),
        )
        with pytest.raises(ValidationFailedError):
            await inventory_service.adjust(
                db_session, material_id=material.id, quantity=Decimal("-5"), idempotency_key=uuid.uuid4()
            )


class TestValidation:
    async def test_zero_quantity_rejected(self, db_session, material):
        with pytest.raises(ValidationFailedError):
            await inventory_service.purchase(
                db_session, material_id=material.id, quantity=Decimal("0"), idempotency_key=uuid.uuid4()
            )

    async def test_negative_quantity_rejected_except_adjust(self, db_session, material):
        with pytest.raises(ValidationFailedError):
            await inventory_service.purchase(
                db_session, material_id=material.id, quantity=Decimal("-1"), idempotency_key=uuid.uuid4()
            )

    async def test_unknown_material_rejected(self, db_session):
        with pytest.raises(ValidationFailedError):
            await inventory_service.purchase(
                db_session, material_id=uuid.uuid4(), quantity=Decimal("1"), idempotency_key=uuid.uuid4()
            )

    async def test_inactive_material_rejected(self, db_session, material):
        material.is_active = False
        await db_session.commit()
        with pytest.raises(ValidationFailedError):
            await inventory_service.purchase(
                db_session, material_id=material.id, quantity=Decimal("1"), idempotency_key=uuid.uuid4()
            )


class TestIdempotency:
    async def test_same_key_same_payload_replays_without_double_apply(self, db_session, material):
        key = uuid.uuid4()
        first = await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=key
        )
        second = await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=key
        )
        assert second.movement.id == first.movement.id
        assert second.stock_level.on_hand == Decimal("10")

        from sqlalchemy import func, select

        from app.models.inventory import StockMovement

        count = (
            await db_session.execute(
                select(func.count()).select_from(StockMovement).where(StockMovement.idempotency_key == key)
            )
        ).scalar_one()
        assert count == 1

    async def test_same_key_different_payload_conflicts(self, db_session, material):
        key = uuid.uuid4()
        await inventory_service.purchase(
            db_session, material_id=material.id, quantity=Decimal("10"), idempotency_key=key
        )
        with pytest.raises(ConflictError):
            await inventory_service.purchase(
                db_session, material_id=material.id, quantity=Decimal("5"), idempotency_key=key
            )


class TestModelRegistration:
    def test_inventory_tables_registered_on_metadata(self):
        import app.models  # noqa: F401
        from app.db.base import Base

        assert "stock_levels" in Base.metadata.tables
        assert "stock_movements" in Base.metadata.tables
        assert "production_orders" in Base.metadata.tables
        assert "production_material_reservations" in Base.metadata.tables
