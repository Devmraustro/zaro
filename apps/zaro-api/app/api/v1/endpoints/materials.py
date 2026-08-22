"""Admin materials endpoints: CRUD + append-only price history."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, require_permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import Permission
from app.models.user import User
from app.schemas.materials import (
    MaterialCreate,
    MaterialPriceCreate,
    MaterialUpdate,
)
from app.services import materials_service
from app.services.audit import record_event

router = APIRouter(prefix="/admin/materials", tags=["materials"])


def _serialize_price(price) -> dict[str, Any]:
    return {
        "id": str(price.id),
        "material_id": str(price.material_id),
        "effective_from": price.effective_from.isoformat(),
        "unit_price_minor": price.unit_price_minor,
        "currency": price.currency,
        "created_at": price.created_at.isoformat() if price.created_at else None,
    }


async def _serialize_material(db: AsyncSession, material) -> dict[str, Any]:
    prices = await materials_service.list_prices(db, material.id)
    return {
        "id": str(material.id),
        "name": material.name,
        "code": material.code,
        "category": str(material.category),
        "unit": str(material.unit),
        "is_active": material.is_active,
        "notes": material.notes,
        "created_at": material.created_at.isoformat() if material.created_at else None,
        "updated_at": material.updated_at.isoformat() if material.updated_at else None,
        "prices": [_serialize_price(p) for p in prices],
    }


@router.post("", status_code=201)
async def create_material(
    payload: MaterialCreate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.MATERIALS_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    material = await materials_service.create_material(
        db,
        name=payload.name,
        code=payload.code,
        category=payload.category,
        unit=payload.unit,
        notes=payload.notes,
    )
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.MATERIAL_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="material",
        resource_id=str(material.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"code": material.code},
    )
    await db.commit()
    return await _serialize_material(db, material)


@router.get("")
async def list_materials(
    _user: Annotated[User, Depends(require_permission(Permission.MATERIALS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = True,
) -> list[dict[str, Any]]:
    materials = await materials_service.list_materials(db, include_inactive=include_inactive)
    return [await _serialize_material(db, m) for m in materials]


@router.get("/{material_id}")
async def get_material(
    material_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.MATERIALS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    material = await materials_service.get_material(db, material_id)
    return await _serialize_material(db, material)


@router.patch("/{material_id}")
async def update_material(
    material_id: UUID,
    payload: MaterialUpdate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.MATERIALS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    material = await materials_service.get_material(db, material_id)
    changes = payload.model_dump(exclude_unset=True)
    material = await materials_service.update_material(db, material, changes)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.MATERIAL_UPDATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="material",
        resource_id=str(material.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"fields": sorted(changes.keys())},
    )
    await db.commit()
    return await _serialize_material(db, material)


@router.post("/{material_id}/prices", status_code=201)
async def add_material_price(
    material_id: UUID,
    payload: MaterialPriceCreate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.MATERIALS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    material = await materials_service.get_material(db, material_id)
    previous = await materials_service.resolve_unit_price_minor(db, material.id)
    price = await materials_service.add_price(
        db,
        material,
        unit_price_minor=payload.unit_price_minor,
        currency=payload.currency,
        effective_from=payload.effective_from,
        created_by=user.id,
    )
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.MATERIAL_PRICE_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="material",
        resource_id=str(material.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "price_id": str(price.id),
            "effective_from": price.effective_from.isoformat(),
            "previous_minor": previous,
            "new_minor": price.unit_price_minor,
        },
    )
    await db.commit()
    return _serialize_price(price)
