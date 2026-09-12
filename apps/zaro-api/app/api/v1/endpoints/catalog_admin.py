"""Admin catalog endpoints: categories, products, variants.

Authorization model:

- create/publish/archive/price require distinct permissions so the RBAC
  matrix stays meaningful (e.g. CONTENT can draft but not price);
- price changes additionally audit old/new values;
- mass assignment is structurally impossible: request schemas use
  extra=forbid and protected fields are simply not present in them.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _get_request_context, require_permission
from app.db.session import get_db
from app.models.audit_enums import AuditAction, AuditResult
from app.models.enums import Permission
from app.models.user import User
from app.schemas.catalog import (
    CategoryAdminResponse,
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductPriceSet,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.services import catalog_service
from app.services.audit import record_event

router = APIRouter(prefix="/admin", tags=["admin-catalog"])


def _serialize_product_admin(product) -> dict[str, Any]:
    base = {
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
        "status": str(product.status),
        "variants": [
            {
                "id": str(v.id),
                "sku": v.sku,
                "label": v.label,
                "attributes": v.attributes,
                "price_override_minor": v.price_override_minor,
                "is_active": v.is_active,
                "sort_order": v.sort_order,
            }
            for v in sorted(product.variants, key=lambda x: x.sort_order)
        ],
        "media": [],
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }
    return base


# --- Categories ---------------------------------------------------------------


@router.post("/categories", response_model=CategoryAdminResponse, status_code=201)
async def create_category(
    payload: CategoryCreate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryAdminResponse:
    category = await catalog_service.create_category(
        db, name=payload.name, description=payload.description, sort_order=payload.sort_order
    )
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.CATEGORY_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="category",
        resource_id=str(category.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"slug": category.slug},
    )
    await db.commit()
    return CategoryAdminResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.patch("/categories/{category_id}", response_model=CategoryAdminResponse)
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryAdminResponse:
    category = await catalog_service.get_category(db, category_id)
    changes = payload.model_dump(exclude_unset=True)
    category = await catalog_service.update_category(db, category, changes)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.CATEGORY_UPDATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="category",
        resource_id=str(category.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"fields": sorted(changes.keys())},
    )
    await db.commit()
    return CategoryAdminResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.get("/categories", response_model=list[CategoryAdminResponse])
async def list_categories_admin(
    _user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryAdminResponse]:
    categories = await catalog_service.list_categories(db, include_inactive=True)
    return [
        CategoryAdminResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            sort_order=c.sort_order,
            is_active=c.is_active,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in categories
    ]


# --- Products -----------------------------------------------------------------


@router.post("/products", status_code=201)
async def create_product(
    payload: ProductCreate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    product = await catalog_service.create_product(db, payload, actor_user_id=user.id)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="product",
        resource_id=str(product.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"product_code": product.product_code},
    )
    await db.commit()
    return _serialize_product_admin(product)


@router.get("/products")
async def list_products_admin(
    _user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query(pattern=r"^(draft|active|archived)$")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> dict[str, Any]:
    products, total = await catalog_service.list_admin_products(
        db, page=page, page_size=page_size, status=status, search=search
    )
    return {
        "items": [_serialize_product_admin(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_previous": page > 1,
    }


@router.get("/products/{product_id}")
async def get_product_admin(
    product_id: UUID,
    _user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    product = await catalog_service.get_product(db, product_id)
    return _serialize_product_admin(product)


@router.patch("/products/{product_id}")
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    product = await catalog_service.get_product(db, product_id)
    changes = payload.model_dump(exclude_unset=True)
    product = await catalog_service.update_product(db, product, changes)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_UPDATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="product",
        resource_id=str(product.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"fields": sorted(changes.keys())},
    )
    await db.commit()
    return _serialize_product_admin(product)


@router.post("/products/{product_id}/publish")
async def publish_product(
    product_id: UUID,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    product = await catalog_service.get_product(db, product_id)
    product = await catalog_service.publish_product(db, product)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_PUBLISHED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="product",
        resource_id=str(product.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return _serialize_product_admin(product)


@router.post("/products/{product_id}/archive")
async def archive_product(
    product_id: UUID,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    product = await catalog_service.get_product(db, product_id)
    product = await catalog_service.archive_product(db, product)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_ARCHIVED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="product",
        resource_id=str(product.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return _serialize_product_admin(product)


@router.post("/products/{product_id}/price")
async def set_product_price(
    product_id: UUID,
    payload: ProductPriceSet,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_MANAGE_PRICE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    product = await catalog_service.get_product(db, product_id)
    old_minor, new_minor = catalog_service.set_selling_price(db, product, payload.selling_price_minor, payload.currency)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_PRICE_CHANGED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="product",
        resource_id=str(product.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"old_minor": old_minor, "new_minor": new_minor, "reason": payload.reason},
    )
    await db.commit()
    return _serialize_product_admin(product)


# --- Variants -----------------------------------------------------------------


async def _check_variant_price_authorization(
    request: Request,
    user: User,
    payload_has_price: bool,
) -> None:
    """Variant prices are server-controlled like product prices."""
    if not payload_has_price:
        return
    from app.core.exceptions import ForbiddenError
    from app.core.rbac import has_permission

    if not has_permission(user.role, Permission.PRODUCTS_MANAGE_PRICE):
        raise ForbiddenError("Setting variant prices requires price management permission")


@router.post("/products/{product_id}/variants", response_model=None, status_code=201)
async def create_variant(
    product_id: UUID,
    payload: VariantCreate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    await _check_variant_price_authorization(request, user, payload.price_override_minor is not None)
    product = await catalog_service.get_product(db, product_id)
    variant = await catalog_service.create_variant(db, product, payload)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_VARIANT_CREATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="variant",
        resource_id=str(variant.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"product_id": str(product.id), "sku": variant.sku},
    )
    await db.commit()
    return {
        "id": str(variant.id),
        "sku": variant.sku,
        "label": variant.label,
        "attributes": variant.attributes,
        "price_override_minor": variant.price_override_minor,
        "is_active": variant.is_active,
        "sort_order": variant.sort_order,
    }


@router.patch("/products/{product_id}/variants/{variant_id}")
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    payload: VariantUpdate,
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    await _check_variant_price_authorization(request, user, "price_override_minor" in changes)
    product = await catalog_service.get_product(db, product_id)
    variant = next((v for v in product.variants if v.id == variant_id), None)
    if variant is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Variant not found")
    for field_name, value in changes.items():
        setattr(variant, field_name, value)
    request_id, ip_address, user_agent = _get_request_context(request)
    await record_event(
        db,
        action=AuditAction.PRODUCT_VARIANT_UPDATED,
        result=AuditResult.SUCCESS,
        actor_user_id=user.id,
        resource_type="variant",
        resource_id=str(variant.id),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"product_id": str(product.id), "fields": sorted(changes.keys())},
    )
    await db.commit()
    return {
        "id": str(variant.id),
        "sku": variant.sku,
        "label": variant.label,
        "attributes": variant.attributes,
        "price_override_minor": variant.price_override_minor,
        "is_active": variant.is_active,
        "sort_order": variant.sort_order,
    }
