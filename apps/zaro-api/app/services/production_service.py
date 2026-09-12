"""Production service: production orders, material reservations, and lifecycle management.

Phase 4 MVP: one ProductionOrder per Order. Production operations never modify
financial order totals, deposits, or balance due.

State machine (PRODUCTION_ORDER_TRANSITIONS)::

    PENDING → PLANNED → MATERIALS_RESERVED → IN_PRODUCTION → QUALITY_CHECK → READY → COMPLETED
        ↓              ↓               ↓                ↓                ↓           ↓
      CANCELLED     CANCELLED       CANCELLED        CANCELLED        CANCELLED
                     ↓                                       ↑
                    PLANNED                                   IN_PRODUCTION
                                                            ↓
                                                         PAUSED
        All operations use InventoryService for stock mutations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidStateTransition,
    NotFoundError,
    ValidationFailedError,
)
from app.models.enums import (
    PRODUCTION_MATERIAL_RESERVATION_TRANSITIONS,
    PRODUCTION_ORDER_TRANSITIONS,
    ProductionMaterialReservationStatus,
    ProductionOrderStatus,
    StockMovementType,
)
from app.models.material import Material
from app.models.order import Order
from app.models.production import ProductionMaterialReservation, ProductionOrder

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.order import Order


@dataclass(frozen=True, slots=True)
class MaterialRequirement:
    """Single material requirement derived from an order line."""

    material_id: uuid.UUID
    material_name: str
    material_code: str
    material_unit: str
    quantity_required: Decimal
    unit_price_minor: int
    material_spec: str | None = None


async def get_production_order(db: AsyncSession, production_order_id: uuid.UUID) -> ProductionOrder:
    po = await db.get(ProductionOrder, production_order_id)
    if po is None:
        raise NotFoundError("Production order not found")
    return po


async def get_production_order_for_update(db: AsyncSession, production_order_id: uuid.UUID) -> ProductionOrder:
    """Load and row-lock a production order for a mutating transition.

    Serializes concurrent state-changing operations (e.g. concurrent QC decisions)
    on the same production order row, preventing lost updates and double decisions.
    """
    stmt = select(ProductionOrder).where(ProductionOrder.id == production_order_id).with_for_update()
    po = (await db.execute(stmt)).scalar_one_or_none()
    if po is None:
        raise NotFoundError("Production order not found")
    return po


async def get_material_reservation(db: AsyncSession, reservation_id: uuid.UUID) -> ProductionMaterialReservation:
    mr = await db.get(ProductionMaterialReservation, reservation_id)
    if mr is None:
        raise NotFoundError("Material reservation not found")
    return mr


async def get_material_reservation_for_update(
    db: AsyncSession, reservation_id: uuid.UUID
) -> ProductionMaterialReservation:
    """Load and row-lock a material reservation for a read-modify-write.

    Guards counter updates (consumed/wasted/returned/released) against lost
    updates when the same reservation is mutated concurrently.
    """
    stmt = (
        select(ProductionMaterialReservation)
        .where(ProductionMaterialReservation.id == reservation_id)
        .with_for_update()
    )
    mr = (await db.execute(stmt)).scalar_one_or_none()
    if mr is None:
        raise NotFoundError("Material reservation not found")
    return mr


async def list_production_orders_for_order(db: AsyncSession, order_id: uuid.UUID) -> list[ProductionOrder]:
    """List production orders for a given order (MVP: at most one)."""
    stmt = select(ProductionOrder).where(ProductionOrder.order_id == order_id)
    return list((await db.execute(stmt)).scalars().all())


def validate_production_transition(current: ProductionOrderStatus, target: ProductionOrderStatus) -> None:
    allowed = PRODUCTION_ORDER_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition production order from '{current.value}' to '{target.value}'",
            details={"current": current.value, "allowed": sorted(s.value for s in allowed)},
        )


def validate_reservation_transition(current: str, target: str) -> None:
    current_status = ProductionMaterialReservationStatus(current)
    target_status = ProductionMaterialReservationStatus(target)
    allowed = PRODUCTION_MATERIAL_RESERVATION_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed:
        raise InvalidStateTransition(
            f"Cannot transition material reservation from '{current}' to '{target}'",
            details={"current": current, "allowed": sorted(s.value for s in allowed)},
        )


def compute_remaining_reserved(reservation: ProductionMaterialReservation) -> Decimal:
    """Compute remaining reserved quantity available for consumption."""
    return (
        reservation.quantity_reserved
        - reservation.quantity_consumed
        - reservation.quantity_wasted
        - reservation.quantity_returned
        - reservation.quantity_released
    )


async def _is_idempotent_replay(
    db: AsyncSession,
    *,
    idempotency_key: uuid.UUID,
    material_id: uuid.UUID,
    reference_id: uuid.UUID,
    movement_type: str,
    quantity: Decimal,
) -> bool:
    """True when this exact stock movement was already recorded.

    The inventory layer deduplicates the movement itself, but the
    reservation counters in this module are plain read-modify-writes: without
    this guard a retried request would move stock once yet increment the
    reservation counters twice. A key that exists for a DIFFERENT operation
    is not a replay -- the inventory layer rejects it with 409.
    """
    from app.models.inventory import StockMovement

    stmt = select(StockMovement).where(StockMovement.idempotency_key == idempotency_key)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return False
    existing_type = (
        existing.movement_type.value if hasattr(existing.movement_type, "value") else str(existing.movement_type)
    )
    return (
        existing.material_id == material_id
        and existing.reference_id == reference_id
        and existing_type == movement_type
        and Decimal(str(existing.quantity)) == Decimal(str(quantity))
    )


def _reject_self_approval(po: ProductionOrder, inspector_id: uuid.UUID) -> None:
    """Segregation of duties: an inspector must not QC their own production work.

    A worker/operator who performed production on an order (assigned_worker_id)
    must never be allowed to approve (or otherwise act as inspector on) that same
    order. Enforced server-side; never trust the frontend.
    """
    if po.assigned_worker_id is not None and po.assigned_worker_id == inspector_id:
        raise ForbiddenError("A production worker cannot act as quality inspector on their own production order")


async def create_production_order(
    db: AsyncSession,
    *,
    order: Order,
    created_by: uuid.UUID | None = None,
) -> ProductionOrder:
    """Create a production order from a confirmed order.

    Only allowed when order.status == CONFIRMED.
    Creates the production order and copies financial snapshot from the order.
    """
    from app.services.references import next_production_number

    if order.status != "confirmed":
        raise InvalidStateTransition(
            "Production order can only be created from a confirmed order",
            details={"current": order.status, "required": "confirmed"},
        )

    existing = (
        await db.execute(select(ProductionOrder).where(ProductionOrder.order_id == order.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("A production order already exists for this order")

    from app.services.references import run_with_unique_retry

    async def _insert() -> ProductionOrder:
        # Generate production number
        production_number = await next_production_number(db)

        candidate = ProductionOrder(
            production_number=production_number,
            order_id=order.id,
            customer_id=order.customer_id,
            custom_request_id=order.custom_request_id,
            status=ProductionOrderStatus.PENDING,
            estimated_material_cost_minor=0,
            actual_material_cost_minor=0,
            planned_start_date=None,
            planned_end_date=None,
            assigned_worker_id=None,
            supervisor_id=None,
            qc_inspector_id=None,
            notes=None,
        )
        db.add(candidate)
        await db.flush()
        return candidate

    # Reference collisions regenerate-and-retry; a genuine double create
    # surfaces as 409 via the unique order_id backstop.
    return await run_with_unique_retry(db, _insert, conflict_message="A production order already exists for this order")


async def plan_production(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    requirements: list[MaterialRequirement],
    planned_start_date: datetime | None = None,
    planned_end_date: datetime | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Generate material reservations from order lines (BOM).

    Creates ProductionMaterialReservation records for each requirement.
    Does NOT reserve stock -- that happens in reserve_materials().
    """
    from app.core.money import Money

    po = await get_production_order_for_update(db, production_order_id)

    if ProductionOrderStatus(po.status) != ProductionOrderStatus.PENDING:
        raise InvalidStateTransition(
            "Planning is only allowed from PENDING state",
            details={"current": po.status},
        )

    if not requirements:
        raise ValidationFailedError("At least one material requirement is required")

    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.PLANNED)
    po.status = ProductionOrderStatus.PLANNED
    po.planned_at = datetime.now(UTC)
    po.planned_start_date = planned_start_date
    po.planned_end_date = planned_end_date

    # Estimated material cost with deterministic money rounding (never float
    # math, never int() truncation of fractional minor units).
    total_estimated = 0
    for req in requirements:
        total_estimated += Money(req.unit_price_minor).multiply(req.quantity_required).amount_minor
    po.estimated_material_cost_minor = total_estimated

    # Create material reservations (snapshot at planning time)
    for _idx, req in enumerate(requirements):
        material = await db.get(Material, req.material_id)
        if material is None:
            raise NotFoundError(f"Material {req.material_id} not found")

        mr = ProductionMaterialReservation(
            production_order_id=production_order_id,
            material_id=req.material_id,
            material_name=material.name,
            material_code=material.code,
            material_unit=material.unit.value if hasattr(material.unit, "value") else str(material.unit),
            quantity_required=req.quantity_required,
            unit_price_minor=req.unit_price_minor,
            material_spec=req.material_spec,
            status=ProductionMaterialReservationStatus.PENDING,
            quantity_reserved=0,
            quantity_consumed=0,
            quantity_wasted=0,
            quantity_returned=0,
            quantity_released=0,
        )
        db.add(mr)

    db.add(po)
    await db.flush()
    return po


async def reserve_materials(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProductionOrder:
    """Reserve all materials for a production order (atomic all-or-nothing).

    Uses InventoryService to reserve stock. Locks StockLevel rows in deterministic
    order (material_id ASC) to prevent deadlocks. All-or-nothing: if any material
    is insufficient, entire operation rolls back.
    """
    from app.services import inventory_service

    po = await get_production_order_for_update(db, production_order_id)
    if ProductionOrderStatus(po.status) != ProductionOrderStatus.PLANNED:
        raise InvalidStateTransition(
            "Reservation only allowed from PLANNED state",
            details={"current": po.status},
        )
    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.MATERIALS_RESERVED)

    from app.models.production import ProductionMaterialReservation

    stmt = select(ProductionMaterialReservation).where(
        ProductionMaterialReservation.production_order_id == production_order_id
    )
    reservations = list((await db.execute(stmt)).scalars().all())

    if not reservations:
        raise ValidationFailedError("No material reservations to reserve. Run planning first.")

    # Collect material IDs sorted deterministically (by string representation)
    # for lock ordering. Keep the UUID objects for the actual query filter --
    # casting to str here would fail when binding against the Uuid column.
    material_uuids = sorted((r.material_id for r in reservations), key=str)

    # Lock StockLevel rows in deterministic order
    from app.models.inventory import StockLevel

    stock_stmt = (
        select(StockLevel)
        .where(StockLevel.material_id.in_(material_uuids))
        .with_for_update()
        .order_by(StockLevel.material_id)
    )
    levels = {str(level.material_id): level for level in (await db.execute(stock_stmt)).scalars().all()}

    # Verify all stock available
    for res in reservations:
        level = levels.get(str(res.material_id))
        if level is None:
            # Create stock level if doesn't exist
            level = StockLevel(material_id=res.material_id, on_hand=Decimal("0"), reserved=Decimal("0"))
            db.add(level)
            await db.flush()
            levels[str(res.material_id)] = level
            continue

        available = level.on_hand - level.reserved
        if available < res.quantity_required:
            raise ValidationFailedError(
                f"Insufficient stock for mat {res.material_code}:\n  avail={available},\n  req={res.quantity_required}",
                details={
                    "material_id": str(res.material_id),
                    "available": str(available),
                    "required": str(res.quantity_required),
                },
            )

    # All materials available - apply reservations.
    # Stock accounting (reserved delta + movement + audit) is delegated to
    # InventoryService below; the StockLevel must NOT also be mutated directly
    # here or the reservation would be applied twice on the same ORM object.
    for res in reservations:
        old_status = str(res.status)
        res.quantity_reserved = res.quantity_required
        res.status = ProductionMaterialReservationStatus.RESERVED.value
        if old_status != res.status:
            validate_reservation_transition(old_status, str(res.status))
        res.reserved_at = datetime.now(UTC)

        # Record movement via InventoryService
        await inventory_service.reserve(
            db,
            material_id=res.material_id,
            quantity=res.quantity_required,
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=production_order_id,
            performed_by=actor_user_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    po.status = ProductionOrderStatus.MATERIALS_RESERVED
    po.materials_reserved_at = datetime.now(UTC)
    db.add(po)
    await db.flush()
    return po


async def start_production(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Start production (MATERIALS_RESERVED → IN_PRODUCTION).

    Records the producing actor as the assigned worker when no worker is
    assigned yet, so the QC segregation-of-duties guard can fire on that
    same order. Never overwrites an existing assignment.
    """
    po = await get_production_order_for_update(db, production_order_id)
    if ProductionOrderStatus(po.status) != ProductionOrderStatus.MATERIALS_RESERVED:
        raise InvalidStateTransition(
            "Production can only be started from MATERIALS_RESERVED state",
            details={"current": po.status},
        )
    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.IN_PRODUCTION)
    po.status = ProductionOrderStatus.IN_PRODUCTION
    po.production_started_at = datetime.now(UTC)
    if po.assigned_worker_id is None and actor_user_id is not None:
        po.assigned_worker_id = actor_user_id
    db.add(po)
    await db.flush()
    return po


async def pause_production(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Pause production (IN_PRODUCTION → PAUSED)."""
    po = await get_production_order_for_update(db, production_order_id)
    if ProductionOrderStatus(po.status) != ProductionOrderStatus.IN_PRODUCTION:
        raise InvalidStateTransition(
            "Can only pause from IN_PRODUCTION state",
            details={"current": po.status},
        )
    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.PAUSED)
    po.status = ProductionOrderStatus.PAUSED
    po.paused_at = datetime.now(UTC)
    db.add(po)
    await db.flush()
    return po


async def resume_production(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Resume production (PAUSED → IN_PRODUCTION).

    Like start_production, records the resuming actor as the assigned worker
    when none is recorded yet (e.g. legacy rows), keeping the QC segregation
    guard live. Never overwrites an existing assignment.
    """
    po = await get_production_order_for_update(db, production_order_id)
    if ProductionOrderStatus(po.status) != ProductionOrderStatus.PAUSED:
        raise InvalidStateTransition(
            "Can only resume from PAUSED state",
            details={"current": po.status},
        )
    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.IN_PRODUCTION)
    po.status = ProductionOrderStatus.IN_PRODUCTION
    db.add(po)
    if po.assigned_worker_id is None and actor_user_id is not None:
        po.assigned_worker_id = actor_user_id
    await db.flush()
    return po


async def consume_material(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    material_reservation_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    actor_user_id: uuid.UUID,
    notes: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProductionMaterialReservation:
    """Record material consumption against a production order.

    Validates that consumption does not exceed remaining reserved quantity.
    Updates both ProductionMaterialReservation and StockLevel via InventoryService.
    """
    from app.services import inventory_service

    po = await get_production_order(db, production_order_id)
    if ProductionOrderStatus(po.status) not in (
        ProductionOrderStatus.IN_PRODUCTION,
        ProductionOrderStatus.PAUSED,
    ):
        raise InvalidStateTransition(
            "Consumption only allowed during IN_PRODUCTION or PAUSED state",
            details={"current": po.status},
        )

    mr = await get_material_reservation_for_update(db, material_reservation_id)
    if mr.production_order_id != production_order_id:
        raise ValidationFailedError("Material reservation does not belong to this production order")

    # Idempotent retry comes BEFORE the state gates: a replay performs zero
    # mutation, so even a reservation that has since moved to a terminal
    # status must replay successfully instead of being rejected. A key that
    # belongs to a DIFFERENT operation is not a replay and still falls
    # through to the inventory layer's 409.
    if await _is_idempotent_replay(
        db,
        idempotency_key=idempotency_key,
        material_id=mr.material_id,
        reference_id=production_order_id,
        movement_type=StockMovementType.CONSUME.value,
        quantity=quantity,
    ):
        return mr

    if ProductionMaterialReservationStatus(mr.status) != ProductionMaterialReservationStatus.RESERVED:
        raise InvalidStateTransition(
            "Can only consume from RESERVED reservations",
            details={"current": mr.status},
        )

    remaining = compute_remaining_reserved(mr)
    if quantity > remaining:
        raise ValidationFailedError(
            f"Cannot consume {quantity}, only {remaining} remaining reserved",
            details={"quantity": str(quantity), "remaining": str(remaining)},
        )

    # Record consumption via InventoryService (updates StockLevel). The
    # caller's idempotency key is passed through so retried requests replay
    # instead of double-consuming stock.
    await inventory_service.consume(
        db,
        material_id=mr.material_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        reference_type="production_order",
        reference_id=production_order_id,
        performed_by=actor_user_id,
        actor_user_id=actor_user_id,
        notes=notes,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Update reservation tracking
    old_status = str(mr.status)
    mr.quantity_consumed += quantity
    mr.status = (
        ProductionMaterialReservationStatus.CONSUMED.value
        if mr.quantity_consumed >= mr.quantity_reserved
        else ProductionMaterialReservationStatus.RESERVED.value
    )
    if old_status != mr.status:
        validate_reservation_transition(old_status, str(mr.status))
    if mr.quantity_consumed >= mr.quantity_reserved:
        mr.fully_consumed_at = datetime.now(UTC)
    db.add(mr)
    await db.flush()
    return mr


async def record_waste(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    material_reservation_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProductionMaterialReservation:
    """Record production waste for a reserved material.

    Waste means material was reserved but wasted during production (e.g., cutting errors).
    Reduces both on_hand and reserved.
    """
    from app.services import inventory_service

    po = await get_production_order(db, production_order_id)
    if ProductionOrderStatus(po.status) not in (
        ProductionOrderStatus.IN_PRODUCTION,
        ProductionOrderStatus.PAUSED,
    ):
        raise InvalidStateTransition(
            "Waste can only be recorded during IN_PRODUCTION or PAUSED",
            details={"current": po.status},
        )

    mr = await get_material_reservation_for_update(db, material_reservation_id)
    if mr.production_order_id != production_order_id:
        raise ValidationFailedError("Material reservation does not belong to this production order")

    # Replay check precedes the state gates (see consume_material): retries
    # must succeed even after the reservation reached a terminal status.
    if await _is_idempotent_replay(
        db,
        idempotency_key=idempotency_key,
        material_id=mr.material_id,
        reference_id=production_order_id,
        movement_type=StockMovementType.PRODUCTION_WASTE.value,
        quantity=quantity,
    ):
        return mr

    if ProductionMaterialReservationStatus(mr.status) != ProductionMaterialReservationStatus.RESERVED:
        raise InvalidStateTransition(
            "Waste can only be recorded for RESERVED reservations",
            details={"current": mr.status},
        )

    remaining = compute_remaining_reserved(mr)
    if quantity > remaining:
        raise ValidationFailedError(
            f"Cannot waste {quantity}, only {remaining} remaining reserved",
            details={"quantity": str(quantity), "remaining": str(remaining)},
        )

    # Record waste via InventoryService (production_waste reduces both on_hand and reserved)
    await inventory_service.production_waste(
        db,
        material_id=mr.material_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        reference_type="production_order",
        reference_id=production_order_id,
        performed_by=actor_user_id,
        actor_user_id=actor_user_id,
        notes=reason,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Update reservation tracking
    old_status = str(mr.status)
    mr.quantity_wasted += quantity
    mr.status = (
        ProductionMaterialReservationStatus.CONSUMED.value
        if mr.quantity_wasted + mr.quantity_consumed >= mr.quantity_reserved
        else ProductionMaterialReservationStatus.RESERVED.value
    )
    if old_status != mr.status:
        validate_reservation_transition(old_status, str(mr.status))
    db.add(mr)
    await db.flush()
    return mr


async def return_material(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    material_reservation_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    actor_user_id: uuid.UUID,
    notes: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProductionMaterialReservation:
    """Return unused reserved material to available stock.

    Decreases reserved; on_hand is untouched (the stock never left the shelf).
    """
    from app.services import inventory_service

    po = await get_production_order(db, production_order_id)
    if ProductionOrderStatus(po.status) not in (
        ProductionOrderStatus.IN_PRODUCTION,
        ProductionOrderStatus.PAUSED,
        ProductionOrderStatus.MATERIALS_RESERVED,
    ):
        raise InvalidStateTransition(
            "Return only allowed during production or MATERIALS_RESERVED",
            details={"current": po.status},
        )

    mr = await get_material_reservation_for_update(db, material_reservation_id)
    if mr.production_order_id != production_order_id:
        raise ValidationFailedError("Material reservation does not belong to this production order")

    # Replay check precedes the state gates (see consume_material): retries
    # must succeed even after the reservation reached a terminal status.
    if await _is_idempotent_replay(
        db,
        idempotency_key=idempotency_key,
        material_id=mr.material_id,
        reference_id=production_order_id,
        movement_type=StockMovementType.RETURN.value,
        quantity=quantity,
    ):
        return mr

    remaining = compute_remaining_reserved(mr)
    if quantity > remaining:
        raise ValidationFailedError(
            f"Cannot return {quantity}, only {remaining} available to return",
            details={"quantity": str(quantity), "remaining": str(remaining)},
        )

    # Return via InventoryService (decreases reserved, on_hand untouched)
    await inventory_service.return_material(
        db,
        material_id=mr.material_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        reference_type="production_order",
        reference_id=production_order_id,
        performed_by=actor_user_id,
        actor_user_id=actor_user_id,
        notes=notes,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    old_status = str(mr.status)
    mr.quantity_returned += quantity
    if mr.quantity_returned + mr.quantity_consumed + mr.quantity_wasted >= mr.quantity_reserved:
        mr.status = ProductionMaterialReservationStatus.RELEASED.value
        mr.released_at = datetime.now(UTC)
    if old_status != mr.status:
        validate_reservation_transition(old_status, str(mr.status))
    db.add(mr)
    await db.flush()
    return mr


async def release_material(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    material_reservation_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    actor_user_id: uuid.UUID,
    notes: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProductionMaterialReservation:
    """Release (cancel) part or all of a reservation without physical return.

    Decreases reserved without changing on_hand.
    """
    po = await get_production_order(db, production_order_id)
    if ProductionOrderStatus(po.status) not in (
        ProductionOrderStatus.MATERIALS_RESERVED,
        ProductionOrderStatus.PLANNED,
    ):
        raise InvalidStateTransition(
            "Release only allowed in PLANNED or MATERIALS_RESERVED state",
            details={"current": po.status},
        )

    mr = await get_material_reservation_for_update(db, material_reservation_id)
    if mr.production_order_id != production_order_id:
        raise ValidationFailedError("Material reservation does not belong to this production order")

    # Replay check precedes the state gates (see consume_material): retries
    # must succeed even after the reservation reached a terminal status.
    if await _is_idempotent_replay(
        db,
        idempotency_key=idempotency_key,
        material_id=mr.material_id,
        reference_id=production_order_id,
        movement_type=StockMovementType.RELEASE.value,
        quantity=quantity,
    ):
        return mr

    if ProductionMaterialReservationStatus(mr.status) not in (
        ProductionMaterialReservationStatus.PENDING,
        ProductionMaterialReservationStatus.RESERVED,
    ):
        raise InvalidStateTransition(
            "Can only release PENDING or RESERVED reservations",
            details={"current": mr.status},
        )

    releasable = compute_remaining_reserved(mr)
    if quantity > releasable:
        raise ValidationFailedError(
            f"only {releasable} reserved and not yet released",
            details={"quantity": str(quantity), "available": str(releasable)},
        )

    from app.services import inventory_service

    # Release via InventoryService
    await inventory_service.release(
        db,
        material_id=mr.material_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        reference_type="production_order",
        reference_id=production_order_id,
        performed_by=actor_user_id,
        actor_user_id=actor_user_id,
        notes=notes,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    old_status = str(mr.status)
    mr.quantity_released += quantity
    if compute_remaining_reserved(mr) <= 0:
        mr.status = ProductionMaterialReservationStatus.RELEASED.value
        mr.released_at = datetime.now(UTC)
    if old_status != mr.status:
        validate_reservation_transition(old_status, str(mr.status))
    db.add(mr)
    await db.flush()
    return mr


async def cancel_production(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProductionOrder:
    """Cancel a production order.

    Releases every still-reserved remainder via RELEASE movements. Only the
    unconsumed remainder is released -- consumed/wasted/returned quantities
    already left the reserved pool and must not be released twice.
    """
    po = await get_production_order_for_update(db, production_order_id)
    current = ProductionOrderStatus(po.status)
    validate_production_transition(current, ProductionOrderStatus.CANCELLED)

    # Release all reserved materials (rows locked to serialize against
    # concurrent consume/waste/return operations on the same reservations).
    from app.models.production import ProductionMaterialReservation
    from app.services import inventory_service

    stmt = (
        select(ProductionMaterialReservation)
        .where(ProductionMaterialReservation.production_order_id == production_order_id)
        .with_for_update()
    )
    reservations = list((await db.execute(stmt)).scalars().all())

    for mr in reservations:
        if ProductionMaterialReservationStatus(mr.status) not in (
            ProductionMaterialReservationStatus.PENDING,
            ProductionMaterialReservationStatus.RESERVED,
        ):
            continue
        remaining = compute_remaining_reserved(mr)
        if remaining <= 0:
            continue
        await inventory_service.release(
            db,
            material_id=mr.material_id,
            quantity=remaining,
            idempotency_key=uuid.uuid4(),
            reference_type="production_order",
            reference_id=production_order_id,
            performed_by=actor_user_id,
            actor_user_id=actor_user_id,
            notes=f"Cancelled: {reason}",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        old_status = str(mr.status)
        mr.quantity_released += remaining
        mr.status = ProductionMaterialReservationStatus.RELEASED.value
        mr.released_at = datetime.now(UTC)
        if old_status != mr.status:
            validate_reservation_transition(old_status, str(mr.status))
        db.add(mr)

    po.status = ProductionOrderStatus.CANCELLED.value  # type: ignore[assignment]
    po.cancelled_at = datetime.now(UTC)
    po.cancellation_reason = reason
    db.add(po)
    await db.flush()
    return po


async def complete_production(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Mark production as completed (READY → COMPLETED)."""
    po = await get_production_order_for_update(db, production_order_id)
    if po.status != ProductionOrderStatus.READY.value:
        raise InvalidStateTransition(
            "Can only complete from READY state",
            details={"current": po.status},
        )
    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.COMPLETED)
    po.status = ProductionOrderStatus.COMPLETED.value  # type: ignore[assignment]
    po.completed_at = datetime.now(UTC)
    db.add(po)
    await db.flush()
    return po


async def start_quality_check(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    inspector_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Start quality check (IN_PRODUCTION → QUALITY_CHECK).

    The acting inspector must not be the worker assigned to produce this order
    (segregation of duties). The production order is row-locked so a concurrent
    decision cannot race this transition.
    """
    po = await get_production_order_for_update(db, production_order_id)
    _reject_self_approval(po, inspector_id)
    if po.status != ProductionOrderStatus.IN_PRODUCTION.value:
        raise InvalidStateTransition(
            "Quality check can only be started from IN_PRODUCTION",
            details={"current": po.status},
        )
    # All reserved materials must be accounted for (consumed, wasted,
    # returned or released) before QC: otherwise stock would stay reserved
    # forever against a finished order and availability would drift.
    rows = (
        await db.execute(
            select(ProductionMaterialReservation).where(
                ProductionMaterialReservation.production_order_id == production_order_id
            )
        )
    ).scalars()
    open_rows = [str(r.id) for r in rows if compute_remaining_reserved(r) > 0]
    if open_rows:
        raise ValidationFailedError(
            "All reserved materials must be consumed, wasted, returned or released before quality check",
            details={"open_reservations": open_rows},
        )
    validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.QUALITY_CHECK)
    po.status = ProductionOrderStatus.QUALITY_CHECK.value  # type: ignore[assignment]
    po.quality_check_started_at = datetime.now(UTC)
    po.qc_inspector_id = inspector_id
    db.add(po)
    await db.flush()
    return po


async def complete_quality_check(
    db: AsyncSession,
    production_order_id: uuid.UUID,
    *,
    approved: bool,
    inspector_id: uuid.UUID,
    defects: str | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> ProductionOrder:
    """Complete quality check (QUALITY_CHECK → READY or IN_PRODUCTION).

    The decision is applied atomically under a row lock so exactly one concurrent
    decision wins. The acting inspector must not be the producing worker
    (segregation of duties).
    """
    po = await get_production_order_for_update(db, production_order_id)
    if po.status != ProductionOrderStatus.QUALITY_CHECK.value:
        raise InvalidStateTransition(
            "Quality check can only be completed from QUALITY_CHECK state",
            details={"current": po.status},
        )
    _reject_self_approval(po, inspector_id)
    if approved:
        validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.READY)
        po.status = ProductionOrderStatus.READY.value  # type: ignore[assignment]
        po.ready_at = datetime.now(UTC)
    else:
        # Rework path: back to production for fixes, then a fresh QC round.
        validate_production_transition(ProductionOrderStatus(po.status), ProductionOrderStatus.IN_PRODUCTION)
        po.status = ProductionOrderStatus.IN_PRODUCTION.value  # type: ignore[assignment]
    po.quality_check_completed_at = datetime.now(UTC)
    po.qc_inspector_id = inspector_id
    po.qc_defects = defects
    po.qc_notes = notes
    db.add(po)
    await db.flush()
    return po
