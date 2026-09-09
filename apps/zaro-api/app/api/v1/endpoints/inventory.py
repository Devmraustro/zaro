"""Inventory API endpoints.

Admin-only surface for inventory management.
All mutations go through InventoryService with idempotency and audit.
"""

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, require_permission
from app.core.exceptions import ValidationFailedError
from app.db.session import get_db
from app.models.enums import Permission, StockMovementType
from app.models.inventory import StockMovement
from app.models.user import User
from app.schemas.inventory import (
    AdjustRequest,
    ConsumeRequest,
    InventoryWasteRequest,
    ProductionWasteRequest,
    PurchaseRequest,
    ReleaseRequest,
    ReserveRequest,
    ReturnRequest,
)
from app.services import inventory_service

router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])


def serialize_movement(movement: StockMovement) -> dict[str, Any]:
    return {
        "id": str(movement.id),
        "material_id": str(movement.material_id),
        "movement_type": movement.movement_type.value,
        "quantity": movement.quantity,
        "reference_type": movement.reference_type,
        "reference_id": str(movement.reference_id) if movement.reference_id else None,
        "idempotency_key": str(movement.idempotency_key) if movement.idempotency_key else None,
        "unit_price_minor": movement.unit_price_minor,
        "currency": movement.currency,
        "performed_by": str(movement.performed_by) if movement.performed_by else None,
        "notes": movement.notes,
        "created_at": movement.created_at.isoformat() if movement.created_at else None,
    }


def serialize_stock_level(level, material) -> dict[str, Any]:
    return {
        "material_id": str(level.material_id),
        "material_code": material.code,
        "material_name": material.name,
        "material_unit": material.unit.value,
        "on_hand": level.on_hand,
        "reserved": level.reserved,
        "available": level.available(),
    }


def _build_payload_for_audit(
    payload: Any, movement_type: str, reference_type: str | None = None, reference_id: UUID | None = None
) -> dict:
    """Build audit payload from request model."""
    data = payload.model_dump()
    data["movement_type"] = movement_type
    if reference_type:
        data["reference_type"] = reference_type
    if reference_id:
        data["reference_id"] = str(reference_id)
    return data


async def _apply_movement(
    request: Request,
    db: AsyncSession,
    user: User,
    movement_type: str,
    *,
    material_id: UUID,
    quantity: Decimal,
    idempotency_key: UUID,
    reference_type: str | None,
    reference_id: UUID | None,
    unit_price_minor: int | None,
    currency: str,
    performed_by: UUID | None,
    notes: str | None,
) -> dict:
    """Common handler for recording a movement with audit."""
    from app.services import inventory_service

    # Build payload for idempotency fingerprint
    payload_dict = {
        "material_id": str(material_id),
        "movement_type": movement_type,
        "quantity": str(quantity),
    }
    if reference_type:
        payload_dict["reference_type"] = reference_type
    if reference_id:
        payload_dict["reference_id"] = str(reference_id)
    if unit_price_minor is not None:
        payload_dict["unit_price_minor"] = str(unit_price_minor)
    if currency:
        payload_dict["currency"] = currency

    request_id, ip_address, user_agent = _get_request_context(request)

    if movement_type == "purchase":
        result = await inventory_service.purchase(
            db,
            material_id=material_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            unit_price_minor=unit_price_minor,
            currency=currency,
            reference_type=reference_type or "purchase_order",
            reference_id=reference_id,
            performed_by=performed_by,
            notes=notes,
            actor_user_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    elif movement_type in ("reserve", "release", "consume", "production_waste", "return"):
        # These movement types require reference_type and reference_id
        assert reference_type is not None, f"{movement_type} requires reference_type"
        assert reference_id is not None, f"{movement_type} requires reference_id"
        if movement_type == "reserve":
            result = await inventory_service.reserve(
                db,
                material_id=material_id,
                quantity=quantity,
                idempotency_key=idempotency_key,
                reference_type=reference_type,
                reference_id=reference_id,
                performed_by=performed_by,
                notes=notes,
                actor_user_id=user.id,
            )
        elif movement_type == "release":
            result = await inventory_service.release(
                db,
                material_id=material_id,
                quantity=quantity,
                idempotency_key=idempotency_key,
                reference_type=reference_type,
                reference_id=reference_id,
                performed_by=performed_by,
                notes=notes,
                actor_user_id=user.id,
            )
        elif movement_type == "consume":
            result = await inventory_service.consume(
                db,
                material_id=material_id,
                quantity=quantity,
                idempotency_key=idempotency_key,
                reference_type=reference_type,
                reference_id=reference_id,
                performed_by=performed_by,
                notes=notes,
                actor_user_id=user.id,
            )
        elif movement_type == "production_waste":
            result = await inventory_service.production_waste(
                db,
                material_id=material_id,
                quantity=quantity,
                idempotency_key=idempotency_key,
                reference_type=reference_type,
                reference_id=reference_id,
                performed_by=performed_by,
                notes=notes,
                actor_user_id=user.id,
            )
        elif movement_type == "return":
            result = await inventory_service.return_material(
                db,
                material_id=material_id,
                quantity=quantity,
                idempotency_key=idempotency_key,
                reference_type=reference_type,
                reference_id=reference_id,
                performed_by=performed_by,
                notes=notes,
                actor_user_id=user.id,
            )
    elif movement_type == "inventory_waste":
        result = await inventory_service.inventory_waste(
            db,
            material_id=material_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            performed_by=performed_by,
            notes=notes,
            actor_user_id=user.id,
        )
    elif movement_type == "adjust":
        result = await inventory_service.adjust(
            db,
            material_id=material_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            performed_by=performed_by,
            notes=notes,
            actor_user_id=user.id,
        )
    else:
        raise ValidationFailedError(f"Unknown movement type: {movement_type}")

    await db.commit()
    return {
        "movement_id": str(result.movement.id),
        "stock_level": {"on_hand": str(result.stock_level.on_hand), "reserved": str(result.stock_level.reserved)},
    }


def stock_movement_type_from_str(s: str):
    return StockMovementType(s)


# --- Query endpoints ---


@router.get("", response_model=None)
async def list_stock_levels(
    _user: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List current stock levels for all materials."""
    summary = await inventory_service.get_stock_summary(db)
    return summary


@router.get("/{material_id}", response_model=None)
async def get_stock_level(
    material_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get stock level for a specific material."""
    from app.models.material import Material

    material = await db.get(Material, material_id)
    if material is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Material not found")

    level = await inventory_service.get_stock_level(db, material_id)
    return {
        "material_id": str(level.material_id),
        "material_code": material.code,
        "material_name": material.name,
        "material_unit": material.unit.value,
        "on_hand": level.on_hand,
        "reserved": level.reserved,
        "available": level.available(),
    }


@router.get("/movements", response_model=None)
async def list_movements(
    _user: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    material_id: Annotated[UUID | None, Query()] = None,
    movement_type: Annotated[str | None, Query()] = None,
    reference_type: Annotated[str | None, Query()] = None,
    reference_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, Any]:
    """List stock movements with pagination and filters."""

    movement_type_enum = StockMovementType(movement_type) if movement_type else None

    movements, total = await inventory_service.list_movements(
        db,
        material_id=material_id,
        movement_type=movement_type_enum,
        reference_type=reference_type,
        reference_id=reference_id,
        page=page,
        page_size=page_size,
    )
    items = []
    for m in movements:
        items.append(
            {
                "id": str(m.id),
                "material_id": str(m.material_id),
                "movement_type": m.movement_type.value,
                "quantity": m.quantity,
                "reference_type": m.reference_type,
                "reference_id": str(m.reference_id) if m.reference_id else None,
                "idempotency_key": str(m.idempotency_key) if m.idempotency_key else None,
                "unit_price_minor": m.unit_price_minor,
                "currency": m.currency,
                "performed_by": str(m.performed_by) if m.performed_by else None,
                "notes": m.notes,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


# --- Mutation endpoints ---


@router.post("/purchase", status_code=201)
async def record_purchase(
    request: Request,
    payload: PurchaseRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Record a purchase/receipt of material."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "purchase",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        unit_price_minor=payload.unit_price_minor,
        currency=payload.currency,
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/reserve", status_code=201)
async def record_reserve(
    request: Request,
    payload: ReserveRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Reserve material for a production order."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "reserve",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/release", status_code=201)
async def record_release(
    request: Request,
    payload: ReleaseRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Release a reservation (cancel/reduce without physical stock movement)."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "release",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/consume", status_code=201)
async def record_consume(
    request: Request,
    payload: ConsumeRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Consume reserved material (actual production consumption)."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "consume",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/production-waste", status_code=201)
async def record_production_waste(
    request: Request,
    payload: ProductionWasteRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Record production waste (waste on reserved material)."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "production_waste",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/inventory-waste", status_code=201)
async def record_inventory_waste(
    request: Request,
    payload: InventoryWasteRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Record inventory damage/waste (not on reserved material)."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "inventory_waste",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=None,
        reference_id=None,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/adjust", status_code=201)
async def record_adjust(
    request: Request,
    payload: AdjustRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Adjust stock level (physical count correction)."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "adjust",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=None,
        reference_id=None,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result


@router.post("/return", status_code=201)
async def record_return(
    request: Request,
    payload: ReturnRequest,
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return unused reserved material to available stock."""
    from decimal import Decimal

    result = await _apply_movement(
        request,
        db,
        user,
        "return",
        material_id=payload.material_id,
        quantity=Decimal(payload.quantity),
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        unit_price_minor=None,
        currency="DZD",
        performed_by=None,
        notes=payload.notes,
    )
    return result
