"""Production schemas.

Financial rule: clients may describe WHAT they are planning or recording
but never the computed financials or state transitions.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaterialRequirementIn(BaseModel):
    """Material requirement for production planning."""

    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    quantity: str = Field(
        pattern=r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$",
        description="Decimal quantity (up to 3 decimal places)",
        examples=["10", "2.5"],
    )
    unit_price_minor: int = Field(ge=0, le=10**13)
    material_spec: str | None = Field(default=None, max_length=500)


class ProductionOrderCreate(BaseModel):
    """Admin payload for creating a production order from a confirmed order."""

    model_config = ConfigDict(extra="forbid")

    order_id: UUID


class ProductionOrderPlan(BaseModel):
    """Admin payload for planning a production order (BOM snapshot)."""

    model_config = ConfigDict(extra="forbid")

    requirements: list[MaterialRequirementIn] = Field(min_length=1, max_length=100)
    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None


class ProductionOrderAction(BaseModel):
    """Empty payload for state transitions (extra="forbid" blocks mass assignment)."""

    model_config = ConfigDict(extra="forbid")


class ProductionOrderActionWithNote(ProductionOrderAction):
    """Action payload with optional note."""

    note: str | None = Field(default=None, max_length=2000)


class ProductionOrderCancel(ProductionOrderAction):
    """Cancel payload with mandatory reason."""

    reason: str = Field(min_length=1, max_length=500)


class ProductionConsumeRequest(BaseModel):
    """Consume material from a reservation."""

    model_config = ConfigDict(extra="forbid")

    material_reservation_id: UUID
    quantity: str = Field(
        pattern=r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$",
        description="Decimal quantity (up to 3 decimal places)",
        examples=["5", "2.5"],
    )
    idempotency_key: UUID
    notes: str | None = Field(default=None, max_length=500)


class ProductionWasteRequest(BaseModel):
    """Record production waste."""

    model_config = ConfigDict(extra="forbid")

    material_reservation_id: UUID
    quantity: str = Field(
        pattern=r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$",
        description="Decimal quantity (up to 3 decimal places)",
        examples=["1", "0.5"],
    )
    idempotency_key: UUID
    reason: str | None = Field(default=None, max_length=500)


class ProductionReturnRequest(BaseModel):
    """Return unused reserved material."""

    model_config = ConfigDict(extra="forbid")

    material_reservation_id: UUID
    quantity: str = Field(
        pattern=r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$",
        description="Decimal quantity (up to 3 decimal places)",
        examples=["5", "2.5"],
    )
    idempotency_key: UUID
    notes: str | None = Field(default=None, max_length=500)


class ProductionReleaseRequest(BaseModel):
    """Release (cancel) a reservation without physical return."""

    model_config = ConfigDict(extra="forbid")

    material_reservation_id: UUID
    quantity: str = Field(
        pattern=r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$",
        description="Decimal quantity (up to 3 decimal places)",
        examples=["5", "2.5"],
    )
    idempotency_key: UUID
    notes: str | None = Field(default=None, max_length=500)


class QualityCheckStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Inspector identity is derived from the authenticated user server-side.
    # Intentionally empty body; unknown fields are rejected (mass-assignment guard).


class QualityCheckSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    defects: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


class ProductionMaterialReservationResponse(BaseModel):
    id: UUID
    production_order_id: UUID
    material_id: UUID
    material_name: str
    material_code: str
    material_unit: str
    quantity_required: Decimal
    quantity_reserved: Decimal
    quantity_consumed: Decimal
    quantity_wasted: Decimal
    quantity_returned: Decimal
    quantity_released: Decimal
    unit_price_minor: int
    material_spec: str | None
    status: str
    reserved_at: datetime | None
    released_at: datetime | None
    fully_consumed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductionOrderResponse(BaseModel):
    id: UUID
    production_number: str
    order_id: UUID
    customer_id: UUID | None
    custom_request_id: UUID | None
    status: str
    estimated_material_cost_minor: int
    actual_material_cost_minor: int
    planned_start_date: datetime | None
    planned_end_date: datetime | None
    actual_start_date: datetime | None
    actual_end_date: datetime | None
    assigned_worker_id: UUID | None
    supervisor_id: UUID | None
    qc_inspector_id: UUID | None
    planned_at: datetime | None
    materials_reserved_at: datetime | None
    production_started_at: datetime | None
    paused_at: datetime | None
    quality_check_started_at: datetime | None
    quality_check_completed_at: datetime | None
    ready_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    qc_notes: str | None
    qc_defects: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    material_reservations: list[ProductionMaterialReservationResponse]


class ProductionOrderAdminResponse(ProductionOrderResponse):
    customer_id: UUID | None
    custom_request_id: UUID | None
    notes: str | None
    qc_notes: str | None
    qc_defects: str | None


class PaginatedProductionOrders(BaseModel):
    items: list[ProductionOrderAdminResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
