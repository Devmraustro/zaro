"""Public catalog endpoints (no authentication).

Only ACTIVE products and ACTIVE categories are exposed. Every list is
paginated with allow-listed sort options; free-text search is parameterized
(ILIKE), never string-concatenated SQL.

Multilingual storefront: a ``?lang`` query parameter (en/fr/ar) selects the
display locale, falling back to the ``Accept-Language`` header and then to
English. Product/category display strings are resolved through the
localization tables; canonical English rows remain the fallback.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.localization import CategoryLocalization, ProductLocalization
from app.schemas.catalog import CategoryResponse
from app.services import catalog_service

router = APIRouter(tags=["catalog"])

PUBLIC_LOCALES = ("en", "fr", "ar")


def _resolve_locale(lang: str | None, request: Request) -> str:
    if lang:
        return lang.lower()
    header = request.headers.get("accept-language", "")
    for part in header.split(","):
        base = part.strip().split(";")[0].lower().split("-")[0]
        if base in PUBLIC_LOCALES:
            return base
    return "en"


def _localize(product, localization) -> tuple[str, str | None]:
    """Return (name, description) with the locale override applied."""
    if localization is not None:
        return localization.name, localization.description
    return product.name, product.description


def _serialize_product(product, *, locale: str = "en", localization=None) -> dict:
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
    name, description = _localize(product, localization)
    return {
        "id": str(product.id),
        "name": name,
        "slug": product.slug,
        "product_code": product.product_code,
        "description": description,
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
        "locale": locale,
    }


async def _product_localization_map(db: AsyncSession, product_ids: list, locale: str) -> dict:
    """Localization rows for one locale, keyed by product id (empty for en)."""
    if not product_ids or locale == "en":
        return {}
    rows = (
        (
            await db.execute(
                select(ProductLocalization).where(
                    ProductLocalization.product_id.in_(product_ids), ProductLocalization.locale == locale
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.product_id: row for row in rows}


async def _category_localization_map(db: AsyncSession, category_ids: list, locale: str) -> dict:
    if not category_ids or locale == "en":
        return {}
    rows = (
        (
            await db.execute(
                select(CategoryLocalization).where(
                    CategoryLocalization.category_id.in_(category_ids), CategoryLocalization.locale == locale
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.category_id: row for row in rows}


@router.get("/products")
async def list_products(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(ge=1)] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    featured: bool = False,
    sort: Annotated[str, Query(pattern="^(newest|oldest|name|price_asc|price_desc)$")] = "newest",
    lang: Annotated[str | None, Query(pattern="^(en|fr|ar)$")] = None,
) -> JSONResponse:
    effective_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    locale = _resolve_locale(lang, request)
    products, total = await catalog_service.list_public_products(
        db,
        page=page,
        page_size=effective_page_size,
        category_slug=category,
        search=search,
        featured_only=featured,
        sort=sort,
        lang=locale,
    )
    localizations = await _product_localization_map(db, [p.id for p in products], locale)
    return JSONResponse(
        content={
            "items": [_serialize_product(p, locale=locale, localization=localizations.get(p.id)) for p in products],
            "total": total,
            "page": page,
            "page_size": effective_page_size,
            "has_next": page * effective_page_size < total,
            "has_previous": page > 1,
            "locale": locale,
        }
    )


@router.get("/products/{slug}")
async def get_product_by_slug(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str | None, Query(pattern="^(en|fr|ar)$")] = None,
) -> JSONResponse:
    product = await catalog_service.get_product_by_slug(db, slug)
    if product is None:
        raise NotFoundError("Product not found")
    locale = _resolve_locale(lang, request)
    localizations = await _product_localization_map(db, [product.id], locale)
    return JSONResponse(content=_serialize_product(product, locale=locale, localization=localizations.get(product.id)))


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str | None, Query(pattern="^(en|fr|ar)$")] = None,
) -> list[CategoryResponse]:
    locale = _resolve_locale(lang, request)
    categories = await catalog_service.list_categories(db)
    localizations = await _category_localization_map(db, [c.id for c in categories], locale)
    return [
        CategoryResponse(
            id=c.id,
            name=localizations[c.id].name if c.id in localizations else c.name,
            slug=c.slug,
            description=localizations[c.id].description if c.id in localizations else c.description,
            sort_order=c.sort_order,
            is_active=c.is_active,
        )
        for c in categories
    ]
