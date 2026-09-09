"""Inventory schemas.

Financial rule: clients may describe WHAT they are doing but never the
resulting balances. All stock mutations are server-computed.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StockMovementCreate(BaseModel):
    """Base schema for creating a stock movement."""

    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    idempotency_key: UUID = Field(description="Client-generated UUID for idempotency")
    quantity: str = Field(
        pattern=r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$",
        description="Decimal quantity (positive, up to 3 decimal places)",
        examples=["10", "2.5", "0.1"],
    )


class PurchaseRequest(StockMovementCreate):
    """Record a purchase/receipt of material."""

    unit_price_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="DZD", pattern=r"^[A-Z]{3}$")
    reference_type: str = Field(default="purchase_order", max_length=50)
    reference_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ReserveRequest(StockMovementCreate):
    """Reserve material for a production order."""

    reference_type: str = Field(pattern=r"^(production_order|purchase_order)$")
    reference_id: UUID
    notes: str | None = Field(default=None, max_length=1000)


class ReleaseRequest(StockMovementCreate):
    """Release a reservation (cancel/reduce without physical stock movement)."""

    reference_type: str = Field(pattern=r"^(production_order|purchase_order)$")
    reference_id: UUID
    notes: str | None = Field(default=None, max_length=1000)


class ConsumeRequest(StockMovementCreate):
    """Consume reserved material (actual production consumption)."""

    reference_type: str = Field(pattern=r"^production_order$")
    reference_id: UUID
    notes: str | None = Field(default=None, max_length=1000)


class ProductionWasteRequest(StockMovementCreate):
    """Record production waste (waste on reserved material)."""

    reference_type: str = Field(pattern=r"^production_order$")
    reference_id: UUID
    notes: str | None = Field(default=None, max_length=1000)


class InventoryWasteRequest(StockMovementCreate):
    """Record inventory damage/waste (not on reserved material)."""

    notes: str | None = Field(default=None, max_length=1000)


class AdjustRequest(StockMovementCreate):
    """Adjust stock level (physical count correction)."""

    notes: str | None = Field(default=None, max_length=1000)


class ReturnRequest(StockMovementCreate):
    """Return unused reserved material to available stock."""

    reference_type: str = Field(pattern=r"^production_order$")
    reference_id: UUID
    notes: str | None = Field(default=None, max_length=1000)


class StockLevelResponse(BaseModel):
    """Stock level for a material."""

    material_id: UUID
    material_code: str
    material_name: str
    material_unit: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal


class StockMovementResponse(BaseModel):
    """Stock movement record."""

    id: UUID
    material_id: UUID
    movement_type: str
    quantity: Decimal
    reference_type: str | None
    reference_id: UUID | None
    idempotency_key: UUID | None
    unit_price_minor: int | None
    currency: str
    performed_by: UUID | None
    notes: str | None
    created_at: datetime


class PaginatedMovements(BaseModel):
    items: list[StockMovementResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class StockSummaryResponse(BaseModel):
    material_id: UUID
    material_code: str
    material_name: str
    material_unit: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
