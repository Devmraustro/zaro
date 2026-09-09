"""Inventory service: single entry point for all stock mutations.

All stock mutations MUST go through this service.
No API endpoint or other service may directly mutate StockLevel columns.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationFailedError
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import StockMovementType
from app.models.inventory import StockLevel, StockMovement
from app.models.material import Material
from app.services.audit import record_event
from app.services.references import is_unique_violation

# Deterministic delta vectors for each movement type.
# (on_hand_delta, reserved_delta)
#
# RESERVE never touches on_hand (stock stays physical, only earmarked), so
# RETURN -- "give unused reserved stock back to the available pool" -- must
# only decrement reserved. A (+1, -1) vector here would mint phantom stock
# out of thin air on every return.
_MOVEMENT_DELTAS: dict[StockMovementType, tuple[Decimal, Decimal]] = {
    StockMovementType.PURCHASE: (Decimal("1"), Decimal("0")),
    StockMovementType.RESERVE: (Decimal("0"), Decimal("1")),
    StockMovementType.RELEASE: (Decimal("0"), Decimal("-1")),
    StockMovementType.CONSUME: (Decimal("-1"), Decimal("-1")),
    StockMovementType.PRODUCTION_WASTE: (Decimal("-1"), Decimal("-1")),
    StockMovementType.INVENTORY_WASTE: (Decimal("-1"), Decimal("0")),
    StockMovementType.ADJUST: (Decimal("1"), Decimal("0")),  # signed by qty
    StockMovementType.RETURN: (Decimal("0"), Decimal("-1")),
}


@dataclass(frozen=True, slots=True)
class MovementResult:
    """Result of applying a stock movement."""

    movement: StockMovement
    stock_level: StockLevel
    previous_on_hand: Decimal
    previous_reserved: Decimal


async def get_stock_level(db: AsyncSession, material_id: uuid.UUID) -> StockLevel:
    """Get the stock level for a material, creating it if it doesn't exist."""
    stmt = select(StockLevel).where(StockLevel.material_id == material_id)
    level = (await db.execute(stmt)).scalar_one_or_none()
    if level is None:
        # Create with zero balances (ondelete=RESTRICT on FK ensures material exists)
        level = StockLevel(material_id=material_id, on_hand=Decimal("0"), reserved=Decimal("0"))
        db.add(level)
        await db.flush()
    return level


def _display_str(value: object) -> str:
    """Render a value that may be a str or a StrEnum (fresh DB reads are str)."""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


async def get_stock_level_for_update(db: AsyncSession, material_id: uuid.UUID) -> StockLevel:
    """Get and row-lock the stock level for a material.

    Concurrent first-writes for the same material race on the insert; the
    loser re-reads the winner's row (in a SAVEPOINT so the caller's
    transaction is never poisoned) instead of failing with a 500.
    """
    stmt = select(StockLevel).where(StockLevel.material_id == material_id).with_for_update()
    level = (await db.execute(stmt)).scalar_one_or_none()
    if level is None:
        candidate = StockLevel(material_id=material_id, on_hand=Decimal("0"), reserved=Decimal("0"))
        try:
            async with db.begin_nested():
                db.add(candidate)
                await db.flush()
        except IntegrityError as exc:
            if not is_unique_violation(exc):
                raise
            # Lost the creation race: the winner's row is now visible.
            level = None
        # Re-acquire the row lock on the (possibly just created) row.
        level = (await db.execute(stmt)).scalar_one_or_none()
        if level is None:  # pragma: no cover - defensive; the row must exist now
            raise RuntimeError("Stock level row missing after insert conflict handling")
    return level


async def get_material(db: AsyncSession, material_id: uuid.UUID) -> Material:
    """Get material, raising if not found."""
    material = await db.get(Material, material_id)
    if material is None:
        raise ValidationFailedError("Material not found")
    if not material.is_active:
        raise ValidationFailedError("Material is not active")
    return material


def _compute_fingerprint(payload: dict) -> bytes:
    """Compute SHA256 fingerprint of the request payload."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).digest()


async def _check_idempotency(
    db: AsyncSession, idempotency_key: uuid.UUID, payload_fingerprint: bytes
) -> StockMovement | None:
    """Check if an idempotency key already exists.

    Returns the existing movement if found, None otherwise.
    Raises ConflictError if key exists but fingerprint differs.
    """
    stmt = select(StockMovement).where(StockMovement.idempotency_key == idempotency_key)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != payload_fingerprint:
            raise ConflictError("Idempotency key conflict: same key with different payload")
        return existing
    return None


async def apply_movement(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    movement_type: StockMovementType,
    quantity: Decimal,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    idempotency_key: uuid.UUID,
    payload: dict,
    unit_price_minor: int | None = None,
    currency: str = "DZD",
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Apply a stock movement atomically.

    This is the single entry point for all stock mutations.
    Enforces:
    - Idempotency (same key + same payload = no-op, same key + different payload = 409)
    - Stock invariants (on_hand >= 0, reserved >= 0, reserved <= on_hand)
    - Deterministic delta vectors per movement type
    - Audit logging
    """
    # Validate quantity
    if quantity == 0:
        raise ValidationFailedError("Quantity must not be zero")
    # ADJUST is the only movement type that accepts negative quantities (for reductions)
    if quantity < 0 and movement_type != StockMovementType.ADJUST:
        raise ValidationFailedError("Quantity must be positive (use movement type for direction)")

    # Verify material exists and is active
    await get_material(db, material_id)

    # Compute fingerprint for idempotency check
    fingerprint = _compute_fingerprint(payload)

    # Check idempotency (fast path for retried requests)
    existing = await _check_idempotency(db, idempotency_key, fingerprint)
    if existing is not None:
        # Return existing result without creating a new movement
        level = await get_stock_level(db, material_id)
        return MovementResult(
            movement=existing,
            stock_level=level,
            previous_on_hand=level.on_hand,
            previous_reserved=level.reserved,
        )

    # Row-lock the stock level
    level = await get_stock_level_for_update(db, material_id)

    # Get delta vector
    if movement_type not in _MOVEMENT_DELTAS:
        raise ValidationFailedError(f"Unknown movement type: {movement_type}")
    on_hand_delta, reserved_delta = _MOVEMENT_DELTAS[movement_type]

    # Apply deltas (quantity is always positive; direction comes from movement type)
    new_on_hand = level.on_hand + on_hand_delta * quantity
    new_reserved = level.reserved + reserved_delta * quantity

    # Validate invariants
    if new_on_hand < 0:
        raise ValidationFailedError(
            f"Movement would result in negative on_hand ({new_on_hand})",
            details={"material_id": str(material_id), "current_on_hand": str(level.on_hand)},
        )
    if new_reserved < 0:
        raise ValidationFailedError(
            f"Movement would result in negative reserved ({new_reserved})",
            details={"material_id": str(material_id), "current_reserved": str(level.reserved)},
        )
    if new_reserved > new_on_hand:
        raise ValidationFailedError(
            f"Movement would result in reserved > on_hand (reserved={new_reserved}, on_hand={new_on_hand})",
            details={"material_id": str(material_id)},
        )

    # Capture previous values for audit
    previous_on_hand = level.on_hand
    previous_reserved = level.reserved

    # Create movement record. The mutation runs in a SAVEPOINT: two requests
    # racing with the same idempotency key both pass the fast-path check
    # above, and the loser must observe the winner's row (idempotent replay)
    # instead of dying with a unique violation. Everything mutated inside
    # the savepoint (level balances, new movement) is undone on rollback.
    movement = StockMovement(
        material_id=material_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        unit_price_minor=unit_price_minor,
        currency=currency,
        performed_by=performed_by,
        notes=notes,
    )
    try:
        async with db.begin_nested():
            level.on_hand = new_on_hand
            level.reserved = new_reserved
            db.add(movement)
            db.add(level)
            await db.flush()
    except IntegrityError as exc:
        if not is_unique_violation(exc):
            raise
        raced = await _check_idempotency(db, idempotency_key, fingerprint)
        if raced is None:
            raise
        await db.refresh(level)
        return MovementResult(
            movement=raced,
            stock_level=level,
            previous_on_hand=level.on_hand,
            previous_reserved=level.reserved,
        )

    # Record audit event
    audit_action_map: dict[StockMovementType, AuditAction] = {
        StockMovementType.PURCHASE: AuditAction.MATERIAL_PURCHASED,
        StockMovementType.RESERVE: AuditAction.MATERIAL_RESERVED,
        StockMovementType.RELEASE: AuditAction.MATERIAL_RELEASED,
        StockMovementType.CONSUME: AuditAction.MATERIAL_CONSUMED,
        StockMovementType.PRODUCTION_WASTE: AuditAction.MATERIAL_PRODUCTION_WASTE,
        StockMovementType.INVENTORY_WASTE: AuditAction.MATERIAL_INVENTORY_WASTE,
        StockMovementType.ADJUST: AuditAction.MATERIAL_ADJUSTED,
        StockMovementType.RETURN: AuditAction.MATERIAL_RETURNED,
    }

    if movement_type in audit_action_map:
        await record_event(
            db,
            action=audit_action_map[movement_type],
            result=AuditResult.SUCCESS,
            actor_user_id=actor_user_id,
            resource_type="stock_movement",
            resource_id=str(movement.id),
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "material_id": str(material_id),
                "movement_type": _display_str(movement_type),
                "quantity": str(quantity),
                "unit_price_minor": unit_price_minor,
                "currency": currency,
                "previous_on_hand": str(previous_on_hand),
                "new_on_hand": str(new_on_hand),
                "previous_reserved": str(previous_reserved),
                "new_reserved": str(new_reserved),
                "reference_type": reference_type,
                "reference_id": str(reference_id) if reference_id else None,
            },
        )

    return MovementResult(
        movement=movement,
        stock_level=level,
        previous_on_hand=previous_on_hand,
        previous_reserved=previous_reserved,
    )


async def purchase(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    unit_price_minor: int | None = None,
    currency: str = "DZD",
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    reference_type: str = "purchase_order",
    reference_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Record a purchase/receipt of material."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "purchase",
        "quantity": str(quantity),
        "unit_price_minor": unit_price_minor,
        "currency": currency,
        "reference_type": reference_type,
        "reference_id": str(reference_id) if reference_id else None,
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.PURCHASE,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        unit_price_minor=unit_price_minor,
        currency=currency,
        performed_by=performed_by,
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def reserve(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Reserve material for a production order."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "reserve",
        "quantity": str(quantity),
        "reference_type": reference_type,
        "reference_id": str(reference_id),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.RESERVE,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def release(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Release a reservation (cancel/reduce reservation without physical stock movement)."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "release",
        "quantity": str(quantity),
        "reference_type": reference_type,
        "reference_id": str(reference_id),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.RELEASE,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def consume(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Consume reserved material (actual production consumption)."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "consume",
        "quantity": str(quantity),
        "reference_type": reference_type,
        "reference_id": str(reference_id),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.CONSUME,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def production_waste(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Record production waste (waste on reserved material)."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "production_waste",
        "quantity": str(quantity),
        "reference_type": reference_type,
        "reference_id": str(reference_id),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.PRODUCTION_WASTE,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def inventory_waste(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Record inventory damage/waste (not on reserved material)."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "inventory_waste",
        "quantity": str(quantity),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.INVENTORY_WASTE,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def adjust(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Adjust stock level (physical count correction). Positive or negative delta."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "adjust",
        "quantity": str(quantity),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.ADJUST,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def return_material(
    db: AsyncSession,
    *,
    material_id: uuid.UUID,
    quantity: Decimal,
    idempotency_key: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    performed_by: uuid.UUID | None = None,
    notes: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MovementResult:
    """Return unused reserved material to available stock."""
    payload = {
        "material_id": str(material_id),
        "movement_type": "return",
        "quantity": str(quantity),
        "reference_type": reference_type,
        "reference_id": str(reference_id),
    }
    return await apply_movement(
        db,
        material_id=material_id,
        movement_type=StockMovementType.RETURN,
        quantity=quantity,
        idempotency_key=idempotency_key,
        payload=payload,
        performed_by=performed_by,
        notes=notes,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def list_movements(
    db: AsyncSession,
    *,
    material_id: uuid.UUID | None = None,
    movement_type: StockMovementType | None = None,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[StockMovement], int]:
    """List stock movements with pagination."""
    from sqlalchemy import func

    stmt = select(StockMovement)
    count_stmt = select(func.count()).select_from(StockMovement)

    if material_id is not None:
        stmt = stmt.where(StockMovement.material_id == material_id)
        count_stmt = count_stmt.where(StockMovement.material_id == material_id)
    if movement_type is not None:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
        count_stmt = count_stmt.where(StockMovement.movement_type == movement_type)
    if reference_type is not None:
        stmt = stmt.where(StockMovement.reference_type == reference_type)
        count_stmt = count_stmt.where(StockMovement.reference_type == reference_type)
    if reference_id is not None:
        stmt = stmt.where(StockMovement.reference_id == reference_id)
        count_stmt = count_stmt.where(StockMovement.reference_id == reference_id)

    stmt = stmt.order_by(StockMovement.created_at.desc())
    total = (await db.execute(count_stmt)).scalar_one()
    movements = list((await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all())
    return movements, total


async def get_stock_summary(db: AsyncSession) -> list[dict]:
    """Get stock summary for all materials."""
    stmt = select(StockLevel, Material).join(Material, Material.id == StockLevel.material_id)
    results = (await db.execute(stmt)).all()

    return [
        {
            "material_id": str(level.material_id),
            "material_code": material.code,
            "material_name": material.name,
            "material_unit": _display_str(material.unit),
            "on_hand": str(level.on_hand),
            "reserved": str(level.reserved),
            "available": str(level.available()),
        }
        for level, material in results
    ]
