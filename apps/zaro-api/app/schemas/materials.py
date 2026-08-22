"""Material and price-history schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import MAX_AMOUNT_MINOR


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9\-]*$")
    category: str = Field(pattern=r"^(steel|wood|paint|hardware|consumable|other)$")
    unit: str = Field(pattern=r"^(kg|meter|piece|liter|square_meter|hour)$")
    notes: str | None = Field(default=None, max_length=2000)


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, pattern=r"^(steel|wood|paint|hardware|consumable|other)$")
    unit: str | None = Field(default=None, pattern=r"^(kg|meter|piece|liter|square_meter|hour)$")
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MaterialPriceCreate(BaseModel):
    """Append a new price effective from a point in time. Rows are immutable."""

    model_config = ConfigDict(extra="forbid")

    unit_price_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)
    currency: str = Field(default="DZD", pattern=r"^[A-Z]{3}$")
    effective_from: datetime | None = None  # default: now


class MaterialPriceResponse(BaseModel):
    id: UUID
    material_id: UUID
    effective_from: datetime
    unit_price_minor: int
    currency: str
    created_at: datetime


class MaterialResponse(BaseModel):
    id: UUID
    name: str
    code: str
    category: str
    unit: str
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    prices: list[MaterialPriceResponse] = []
