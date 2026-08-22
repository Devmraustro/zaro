"""Custom request schemas.

Public submission is unauthenticated (website form) and therefore the
strictest-validated surface in this phase: every field length-capped,
contact info shape-checked, budget sanity-checked, extra=forbid.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.money import MAX_AMOUNT_MINOR


class CustomRequestSubmit(BaseModel):
    """Public website form payload."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=6, max_length=20)

    product_type: str = Field(
        pattern=r"^(dining_table|coffee_table|chair|shelf|desk|custom_metalwork|other)$",
    )
    description: str = Field(min_length=10, max_length=4000)
    desired_dimensions: str | None = Field(default=None, max_length=120)
    materials: str | None = Field(default=None, max_length=500)
    colors: str | None = Field(default=None, max_length=200)
    finish: str | None = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=1, le=1000)

    budget_min_minor: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_MINOR)
    budget_max_minor: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_MINOR)


class CustomRequestPublicResponse(BaseModel):
    """What a customer sees about their own request."""

    id: UUID
    reference: str
    product_type: str
    description: str
    desired_dimensions: str | None
    materials: str | None
    colors: str | None
    finish: str | None
    quantity: int
    budget_min_minor: int | None
    budget_max_minor: int | None
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class CustomRequestAdminResponse(CustomRequestPublicResponse):
    """Staff view: adds contact snapshot + internal workflow fields."""

    customer_id: UUID | None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    notes: str | None
    source: str
    assigned_to: UUID | None


class CustomRequestStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(under_review|needs_information|quotation_pending|cancelled|converted)$")
    note: str | None = Field(default=None, max_length=2000)
