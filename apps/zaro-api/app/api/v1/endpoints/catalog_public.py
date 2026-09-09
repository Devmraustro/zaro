"""Public catalog endpoints (no authentication).

Only ACTIVE products and ACTIVE categories are exposed. Every list is
paginated with allow-listed sort options; free-text search is parameterized
(ILIKE), never string-concatenated SQL.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.catalog import CategoryResponse
from app.services import catalog_service

router = APIRouter(tags=["catalog"])


def _serialize_product(product) -> dict:
    variants = [
        {
            "id": str(v.id),
            "sku": v.sku,
            "label": v.label,
            "attributes": v.attributes,
            "effective_price_minor": catalog_service.effective_price_minor(product, v),
            "currency": v.currency,
        }
        for v in product.variants
        if v.is_active
    ]
    media = [
        {
            "id": str(asset.id),
            "url_path": f"/api/v1/files/{asset.id}/public-content",
            "media_kind": asset.media_kind,
            "alt_text": asset.alt_text,
            "sort_order": asset.sort_order,
        }
        for asset in getattr(product, "public_media", [])
    ]
    return {
        "id": str(product.id),
        "name": product.name,
        "slug": product.slug,
        "product_code": product.product_code,
        "description": product.description,
        "category_id": str(product.category_id) if product.category_id else None,
        "dimensions": product.dimensions,
        "materials_spec": product.materials_spec,
        "selling_price_minor": product.selling_price_minor,
        "currency": product.currency,
        "stock_status": product.stock_status,
        "production_time_days": product.production_time_days,
        "delivery_available": product.delivery_available,
        "delivery_info": product.delivery_info,
        "is_featured": product.is_featured,
        "variants": variants,
        "media": media,
    }


@router.get("/products")
async def list_products(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(ge=1)] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    featured: bool = False,
    sort: Annotated[str, Query(pattern="^(newest|oldest|name|price_asc|price_desc)$")] = "newest",
) -> JSONResponse:
    effective_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    products, total = await catalog_service.list_public_products(
        db,
        page=page,
        page_size=effective_page_size,
        category_slug=category,
        search=search,
        featured_only=featured,
        sort=sort,
    )
    return JSONResponse(
        content={
            "items": [_serialize_product(p) for p in products],
            "total": total,
            "page": page,
            "page_size": effective_page_size,
            "has_next": page * effective_page_size < total,
            "has_previous": page > 1,
        }
    )


@router.get("/products/{slug}")
async def get_product_by_slug(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    product = await catalog_service.get_product_by_slug(db, slug)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return JSONResponse(content=_serialize_product(product))


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryResponse]:
    categories = await catalog_service.list_categories(db)
    return [
        CategoryResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            sort_order=c.sort_order,
            is_active=c.is_active,
        )
        for c in categories
    ]
