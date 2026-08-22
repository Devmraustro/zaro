"""Order schemas.

Orders are created exclusively by the server from accepted quotes: there is
no client "create order" payload at all. ``extra="forbid"`` on the cancel
payload blocks mass-assignment of status/deposit fields.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderLineResponse(BaseModel):
    id: UUID
    position: int
    description: str
    quantity: Decimal
    unit_label: str | None
    unit_price_minor: int
    line_total_minor: int


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    quote_id: UUID | None
    custom_request_id: UUID | None
    status: str
    currency: str
    subtotal_minor: int
    discount_minor: int
    delivery_fee_minor: int
    total_minor: int
    deposit_required_minor: int
    deposit_paid_minor: int
    balance_due_minor: int
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineResponse]


class OrderAdminResponse(OrderResponse):
    customer_id: UUID | None
    notes: str | None
    cancellation_reason: str | None


class OrderCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class PaginatedOrders(BaseModel):
    items: list[OrderAdminResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
