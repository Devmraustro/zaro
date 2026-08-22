"""Payment schemas.

The customer can never influence amounts, status, reviewer identity or
references: the deposit-claim request body is EMPTY (``extra="forbid"``), and
rejection reasons are operator-supplied with bounded length.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepositClaimRequest(BaseModel):
    """Intentionally empty: every financial field is server-derived.

    Submitting ``{"amount": 1}`` or ``{"status": "CONFIRMED"}`` here fails
    validation (422) instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")


class PaymentReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(
        pattern=r"^(proof_unreadable|incorrect_amount|incorrect_recipient|duplicate_transfer|invalid_proof|other)$"
    )
    reason_note: str | None = Field(default=None, max_length=500)


class PaymentResponse(BaseModel):
    """Customer-safe payment view."""

    id: UUID
    payment_reference: str
    order_id: UUID
    method: str
    status: str
    amount_minor: int
    currency: str
    ccp_account_holder: str
    ccp_account_identifier: str
    rejection_reason_code: str | None
    rejection_reason_note: str | None
    has_proof: bool
    submitted_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentAdminResponse(PaymentResponse):
    customer_id: UUID | None
    proof_asset_id: UUID | None
    reviewed_by: UUID | None
    proof_uploaded_at: datetime | None


class PaginatedPayments(BaseModel):
    items: list[PaymentAdminResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class PaymentConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_holder: str | None = Field(default=None, min_length=2, max_length=200)
    account_identifier: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = Field(default=None, max_length=2000)
    default_deposit_percentage: int | None = Field(default=None, ge=1, le=100)


class PaymentConfigurationResponse(BaseModel):
    account_holder: str
    account_identifier: str
    instructions: str | None
    default_deposit_percentage: int
    updated_at: datetime | None


class PaymentConfirm(BaseModel):
    """Empty payload for payment confirmation.

    `extra="forbid"` blocks any attempt to inject amount/status/reviewer fields.
    """

    model_config = ConfigDict(extra="forbid")
