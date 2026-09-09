"""Materials service: CRUD + append-only price history.

Price resolution rule: the effective unit price at instant D is the row
with the greatest ``effective_from <= D``. Rows are never updated or
deleted (append-only ledger), so historical cost calculations remain
reproducible forever.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.material import Material, MaterialPrice


async def get_material(db: AsyncSession, material_id: UUID) -> Material:
    material = await db.get(Material, material_id)
    if material is None:
        raise NotFoundError("Material not found")
    return material


async def list_materials(db: AsyncSession, *, include_inactive: bool = True) -> list[Material]:
    stmt = select(Material).order_by(Material.name)
    if not include_inactive:
        stmt = stmt.where(Material.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def create_material(
    db: AsyncSession,
    *,
    name: str,
    code: str,
    category: str,
    unit: str,
    notes: str | None,
) -> Material:
    existing = (await db.execute(select(Material).where(Material.code == code))).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("A material with this code already exists")
    material = Material(name=name, code=code, category=category, unit=unit, notes=notes)
    db.add(material)
    await db.flush()
    return material


async def update_material(db: AsyncSession, material: Material, changes: dict) -> Material:
    for field_name in ("name", "category", "unit", "is_active", "notes"):
        if field_name in changes and changes[field_name] is not None:
            setattr(material, field_name, changes[field_name])
    await db.flush()
    return material


async def add_price(
    db: AsyncSession,
    material: Material,
    *,
    unit_price_minor: int,
    currency: str,
    effective_from: datetime | None,
    created_by: UUID | None,
) -> MaterialPrice:
    from sqlalchemy.exc import IntegrityError

    price = MaterialPrice(
        material_id=material.id,
        effective_from=effective_from or datetime.now(UTC),
        unit_price_minor=unit_price_minor,
        currency=currency,
        created_by=created_by,
    )
    db.add(price)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A price with this effective date already exists for this material") from exc
    return price


async def list_prices(db: AsyncSession, material_id: UUID) -> list[MaterialPrice]:
    stmt = (
        select(MaterialPrice)
        .where(MaterialPrice.material_id == material_id)
        .order_by(MaterialPrice.effective_from.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def resolve_unit_price_minor(db: AsyncSession, material_id: UUID, at: datetime | None = None) -> int | None:
    """Effective minor-unit price at ``at`` (default now), or None when unpriced."""
    at = at or datetime.now(UTC)
    stmt = (
        select(MaterialPrice.unit_price_minor)
        .where(MaterialPrice.material_id == material_id, MaterialPrice.effective_from <= at)
        .order_by(MaterialPrice.effective_from.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
