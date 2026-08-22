"""Quote schemas.

Financial rule mirrored here: clients may describe WHAT they are quoting
(lines, discounts, delivery fee, validity) but never the computed totals or
deposit -- those are server-derived. ``extra="forbid"`` blocks mass-assignment
of status/timestamps/approval fields.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import MAX_AMOUNT_MINOR

# Decimal-as-string policy (no floats): up to 9 integer digits, 3 fraction.
_QTY_PATTERN = r"^(0|[1-9]\d{0,6})(\.\d{1,3})?$"


class QuoteLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=300)
    # Decimal-as-string policy (no floats): up to 7 integer digits, 3 fraction digits.
    quantity: str = Field(pattern=_QTY_PATTERN, examples=["1", "2.5"])
    unit_label: str | None = Field(default=None, max_length=30)
    unit_price_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)

    def to_input(self):
        from app.services.quotes_service import QuoteLineInput

        return QuoteLineInput.build(
            description=self.description,
            quantity=self.quantity,
            unit_label=self.unit_label,
            unit_price_minor=self.unit_price_minor,
        )


class QuoteCreate(BaseModel):
    """Admin payload describing commercial terms (never final amounts)."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None
    custom_request_id: UUID | None = None
    lines: list[QuoteLineIn] = Field(min_length=1, max_length=50)
    discount_minor: int = Field(default=0, ge=0, le=MAX_AMOUNT_MINOR)
    delivery_fee_minor: int = Field(default=0, ge=0, le=MAX_AMOUNT_MINOR)
    deposit_percentage: int | None = Field(default=None, ge=1, le=100)
    valid_until: datetime
    notes: str | None = Field(default=None, max_length=2000)


class QuoteLineResponse(BaseModel):
    id: UUID
    position: int
    description: str
    quantity: Decimal
    unit_label: str | None
    unit_price_minor: int
    line_total_minor: int


class QuoteResponse(BaseModel):
    """Customer-safe view: no internal notes, no staff bookkeeping."""

    id: UUID
    quote_number: str
    custom_request_id: UUID | None
    status: str
    currency: str
    subtotal_minor: int
    discount_minor: int
    delivery_fee_minor: int
    total_minor: int
    deposit_percentage: int
    deposit_amount_minor: int
    balance_amount_minor: int
    valid_until: datetime
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_expired: bool
    lines: list[QuoteLineResponse]


class QuoteAdminResponse(QuoteResponse):
    """Staff view: adds internal workflow fields."""

    customer_id: UUID | None
    notes: str | None
    created_by: UUID | None
    sent_at: datetime | None
    viewed_at: datetime | None
    rejected_at: datetime | None
    cancelled_at: datetime | None


class PaginatedQuotes(BaseModel):
    items: list[QuoteAdminResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class QuoteAction(BaseModel):
    """Empty payload for explicit quote actions (accept/reject/send/cancel).

    `extra="forbid"` ensures clients cannot sneak in fields like
    "status", "amount", "deposit_amount_minor", etc.
    """

    model_config = ConfigDict(extra="forbid")
