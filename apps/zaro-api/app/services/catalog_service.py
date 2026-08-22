"""Catalog service: categories, products, variants.

Business rules enforced here (not in endpoints):

- ``product_code``, ``slug``, ``status`` and price are server-controlled;
  clients can never set them through create/update payloads.
- Only ACTIVE products are publicly visible; drafts/archived 404 publicly.
- Publishing requires a positive selling price and at least one public
  hero/gallery media item OR explicit override flag -- V1: price only
  (media optional), documented in the phase report.
- Price changes are audited with old/new values by the endpoint layer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.category import Category
from app.models.enums import FilePurpose, FileVisibility, ProductStatus
from app.models.file_asset import FileAsset
from app.models.product import Product, ProductVariant
from app.services.references import build_variant_sku, next_product_code, slugify, unique_slug

# --- Categories ---------------------------------------------------------------


async def get_category(db: AsyncSession, category_id: UUID) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    return category


async def create_category(db: AsyncSession, *, name: str, description: str | None, sort_order: int) -> Category:
    slug = await unique_slug(db, Category, slugify(name))
    category = Category(name=name, slug=slug, description=description, sort_order=sort_order)
    db.add(category)
    await db.flush()
    return category


async def update_category(db: AsyncSession, category: Category, changes: dict) -> Category:
    if "name" in changes and changes["name"] and changes["name"] != category.name:
        category.name = changes["name"]
        category.slug = await unique_slug(db, Category, slugify(changes["name"]), exclude_id=category.id)
    for field_name in ("description", "sort_order", "is_active"):
        if field_name in changes and changes[field_name] is not None:
            setattr(category, field_name, changes[field_name])
    await db.flush()
    return category


async def list_categories(db: AsyncSession, *, include_inactive: bool = False) -> list[Category]:
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


# --- Products -----------------------------------------------------------------


def _dimensions_dict(dimensions) -> dict | None:
    if dimensions is None:
        return None
    data = dimensions.model_dump()
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = float(value)
    return data


def _materials_spec_list(materials_spec) -> list[dict] | None:
    if materials_spec is None:
        return None
    return [item.model_dump() for item in materials_spec]


async def create_product(db: AsyncSession, payload, *, actor_user_id: UUID) -> Product:
    category = None
    if payload.category_id is not None:
        category = await get_category(db, payload.category_id)

    slug = await unique_slug(db, Product, slugify(payload.name))
    product_code = await next_product_code(db, category.name if category else None)

    product = Product(
        name=payload.name,
        slug=slug,
        product_code=product_code,
        description=payload.description,
        category_id=payload.category_id,
        dimensions=_dimensions_dict(payload.dimensions),
        materials_spec=_materials_spec_list(payload.materials_spec),
        weight_kg=payload.weight_kg,
        production_time_days=payload.production_time_days,
        stock_status=payload.stock_status,
        delivery_available=payload.delivery_available,
        delivery_info=payload.delivery_info,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        status=ProductStatus.DRAFT,
        created_by=actor_user_id,
    )
    # Initialize the collection in memory so post-flush/commit serialization
    # never triggers a synchronous lazy load inside async context.
    product.variants = []
    db.add(product)
    await db.flush()
    return product


async def get_product(db: AsyncSession, product_id: UUID) -> Product:
    stmt = select(Product).where(Product.id == product_id).options(selectinload(Product.variants))
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product is None:
        raise NotFoundError("Product not found")
    return product


async def get_product_by_slug(db: AsyncSession, slug: str) -> Product | None:
    stmt = (
        select(Product)
        .where(Product.slug == slug, Product.status == ProductStatus.ACTIVE)
        .options(selectinload(Product.variants))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def update_product(db: AsyncSession, product: Product, changes: dict) -> Product:
    if changes.get("name") and changes["name"] != product.name:
        product.name = changes["name"]
        product.slug = await unique_slug(db, Product, slugify(changes["name"]), exclude_id=product.id)
    if "category_id" in changes:
        new_category_id = changes["category_id"]
        if new_category_id is not None:
            await get_category(db, new_category_id)  # existence check
        product.category_id = new_category_id
    if "dimensions" in changes:
        product.dimensions = _dimensions_dict(changes["dimensions"])
    if "materials_spec" in changes:
        product.materials_spec = _materials_spec_list(changes["materials_spec"])
    for field_name in (
        "description",
        "weight_kg",
        "production_time_days",
        "stock_status",
        "delivery_available",
        "delivery_info",
        "meta_title",
        "meta_description",
    ):
        if field_name in changes and changes[field_name] is not None:
            setattr(product, field_name, changes[field_name])
    await db.flush()
    return product


def set_selling_price(db: AsyncSession, product: Product, price_minor: int, currency: str) -> tuple[int, int]:
    """Mutate the price; returns (old_minor, new_minor) for audit purposes."""
    old = product.selling_price_minor
    product.selling_price_minor = price_minor
    product.currency = currency
    return old, price_minor


async def publish_product(db: AsyncSession, product: Product) -> Product:
    if product.status == ProductStatus.ACTIVE:
        raise ConflictError("Product is already active")
    if product.status == ProductStatus.ARCHIVED:
        raise InvalidProductState("Archived products cannot be re-published; restore via update first")
    if product.selling_price_minor <= 0:
        raise ValidationFailedError("Set a positive selling price before publishing")
    product.status = ProductStatus.ACTIVE
    await db.flush()
    return product


class InvalidProductState(ConflictError):
    code = "invalid_product_state"


async def archive_product(db: AsyncSession, product: Product) -> Product:
    if product.status == ProductStatus.ARCHIVED:
        raise ConflictError("Product is already archived")
    product.status = ProductStatus.ARCHIVED
    await db.flush()
    return product


# --- Variants -----------------------------------------------------------------


async def create_variant(db: AsyncSession, product: Product, payload) -> ProductVariant:
    sku = build_variant_sku(product.product_code, len(product.variants))
    variant = ProductVariant(
        product_id=product.id,
        sku=sku,
        label=payload.label,
        attributes=payload.attributes,
        price_override_minor=payload.price_override_minor,
        sort_order=payload.sort_order,
    )
    db.add(variant)
    await db.flush()
    product.variants.append(variant)
    return variant


def effective_price_minor(product: Product, variant: ProductVariant) -> int:
    return variant.price_override_minor if variant.price_override_minor is not None else product.selling_price_minor


# --- Public listing -----------------------------------------------------------


async def list_public_products(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    category_slug: str | None = None,
    search: str | None = None,
    featured_only: bool = False,
    sort: str = "newest",
) -> tuple[list[Product], int]:
    stmt = select(Product).where(Product.status == ProductStatus.ACTIVE)
    count_stmt = select(func.count()).select_from(Product).where(Product.status == ProductStatus.ACTIVE)

    if category_slug:
        category = (await db.execute(select(Category).where(Category.slug == category_slug))).scalar_one_or_none()
        if category is None:
            return [], 0
        stmt = stmt.where(Product.category_id == category.id)
        count_stmt = count_stmt.where(Product.category_id == category.id)

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))

    if featured_only:
        stmt = stmt.where(Product.is_featured.is_(True))
        count_stmt = count_stmt.where(Product.is_featured.is_(True))

    order_map: dict[str, ColumnElement[Any]] = {
        "newest": Product.created_at.desc(),
        "oldest": Product.created_at.asc(),
        "name": Product.name.asc(),
        "price_asc": Product.selling_price_minor.asc(),
        "price_desc": Product.selling_price_minor.desc(),
    }
    stmt = stmt.order_by(order_map[sort])

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        (await db.execute(stmt.options(selectinload(Product.variants)).limit(page_size).offset((page - 1) * page_size)))
        .scalars()
        .all()
    )

    products = list(rows)
    # Attach public media in one query to avoid N+1.
    if products:
        media_stmt = (
            select(FileAsset)
            .where(
                FileAsset.product_id.in_([p.id for p in products]),
                FileAsset.purpose == FilePurpose.PRODUCT_MEDIA,
                FileAsset.visibility == FileVisibility.PUBLIC,
            )
            .order_by(FileAsset.sort_order, FileAsset.created_at)
        )
        media_by_product: dict[UUID, list[FileAsset]] = {}
        for asset in (await db.execute(media_stmt)).scalars().all():
            if asset.product_id is not None:  # filtered by query, but keeps types honest
                media_by_product.setdefault(asset.product_id, []).append(asset)
        for p in products:
            p.public_media = media_by_product.get(p.id, [])  # type: ignore[attr-defined]
    return products, total


async def list_admin_products(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    search: str | None = None,
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)
    if status:
        stmt = stmt.where(Product.status == status)
        count_stmt = count_stmt.where(Product.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(Product.name.ilike(pattern))
        count_stmt = count_stmt.where(Product.name.ilike(pattern))
    stmt = stmt.order_by(Product.created_at.desc())

    total = (await db.execute(count_stmt)).scalar_one()
    products = list(
        (await db.execute(stmt.options(selectinload(Product.variants)).limit(page_size).offset((page - 1) * page_size)))
        .scalars()
        .all()
    )
    return products, total
