"""Catalog schemas: categories, products, variants.

Strict separation between public and admin representations:

- Public schemas expose ONLY what a storefront visitor may see. Cost,
  internal notes, draft/archived products and non-public media never
  appear here -- not even as null fields.
- Admin schemas are for staff tooling.
- All input models use ``extra="forbid"`` so clients cannot smuggle
  protected fields (product_code, status, price, slug, timestamps).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import MAX_AMOUNT_MINOR


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=10000)


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    sort_order: int
    is_active: bool


class DimensionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: Decimal = Field(gt=0, le=100000)
    height: Decimal | None = Field(default=None, gt=0, le=100000)
    depth: Decimal | None = Field(default=None, gt=0, le=100000)
    unit: str = Field(default="cm", pattern=r"^(cm|mm|m|in)$")


class MaterialSpecInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    grade: str | None = Field(default=None, max_length=60)
    finish: str | None = Field(default=None, max_length=60)


class ProductCreate(BaseModel):
    """Admin product creation.

    Protected fields (product_code, slug, status) are server-generated;
    price goes through the dedicated price endpoint so every change is
    authorized and audited.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    category_id: UUID | None = None
    dimensions: DimensionsInput | None = None
    materials_spec: list[MaterialSpecInput] | None = Field(default=None, max_length=50)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=100000)
    production_time_days: int | None = Field(default=None, ge=0, le=3650)
    stock_status: str = Field(default="made_to_order", pattern=r"^(in_stock|made_to_order|out_of_stock)$")
    delivery_available: bool = True
    delivery_info: str | None = Field(default=None, max_length=2000)
    meta_title: str | None = Field(default=None, max_length=200)
    meta_description: str | None = Field(default=None, max_length=500)


class ProductUpdate(BaseModel):
    """Explicit allow-list update; absent fields stay unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    category_id: UUID | None = None
    dimensions: DimensionsInput | None = None
    materials_spec: list[MaterialSpecInput] | None = Field(default=None, max_length=50)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=100000)
    production_time_days: int | None = Field(default=None, ge=0, le=3650)
    stock_status: str | None = Field(default=None, pattern=r"^(in_stock|made_to_order|out_of_stock)$")
    delivery_available: bool | None = None
    delivery_info: str | None = Field(default=None, max_length=2000)
    meta_title: str | None = Field(default=None, max_length=200)
    meta_description: str | None = Field(default=None, max_length=500)


class ProductPriceSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selling_price_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)
    currency: str = Field(default="DZD", pattern=r"^[A-Z]{3}$")
    reason: str | None = Field(default=None, max_length=500)


class VariantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    attributes: dict[str, str] | None = Field(default=None, max_length=20)
    price_override_minor: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_MINOR)
    sort_order: int = Field(default=0, ge=0, le=10000)


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=200)
    attributes: dict[str, str] | None = Field(default=None, max_length=20)
    price_override_minor: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_MINOR)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


# --- Responses ---------------------------------------------------------------


class VariantPublicResponse(BaseModel):
    id: UUID
    sku: str
    label: str
    attributes: dict[str, str] | None
    effective_price_minor: int
    currency: str


class MediaPublicResponse(BaseModel):
    id: UUID
    url_path: str  # /api/v1/files/{id}/content?token=... style path or public path
    media_kind: str
    alt_text: str | None
    sort_order: int


class ProductPublicResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    product_code: str
    description: str | None
    category_id: UUID | None
    dimensions: dict | None
    materials_spec: list | None
    selling_price_minor: int
    currency: str
    stock_status: str
    production_time_days: int | None
    delivery_available: bool
    delivery_info: str | None
    is_featured: bool
    variants: list[VariantPublicResponse]
    media: list[MediaPublicResponse]


class ProductAdminResponse(ProductPublicResponse):
    status: str
    created_at: datetime
    updated_at: datetime


class CategoryAdminResponse(CategoryResponse):
    created_at: datetime
    updated_at: datetime
