"""Cost-engine request/response schemas.

Cost data is commercially sensitive: the endpoint is restricted to
roles with ``products.manage_price`` (owner/admin) and responses are
never exposed through public or general staff product endpoints.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import MAX_AMOUNT_MINOR


class MaterialLineSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(gt=0, le=Decimal("1000000"))
    unit: str = Field(min_length=1, max_length=20)
    unit_price_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)
    waste_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class LaborLineSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    hours: Decimal = Field(ge=0, le=Decimal("100000"))
    hourly_rate_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)


class ExpenseLineSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)
    line_type: str = Field(pattern=r"^(consumable|overhead|packaging)$")
    amount_minor: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_MINOR)
    percent_of_production_cost: Decimal | None = Field(default=None, ge=0, le=100)


class PricingPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(pattern=r"^(target_margin|markup|manual)$")
    target_margin_percent: Decimal | None = Field(default=None, ge=0, lt=100)
    markup_percent: Decimal | None = Field(default=None, ge=0, le=1000)
    manual_selling_price_minor: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_MINOR)


class CostEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_lines: list[MaterialLineSchema] = Field(max_length=200)
    labor_lines: list[LaborLineSchema] = Field(max_length=100)
    expense_lines: list[ExpenseLineSchema] = Field(max_length=50)
    pricing: PricingPolicySchema


class CostLineResponse(BaseModel):
    line_type: str
    label: str
    quantity: Decimal | None
    unit: str | None
    unit_price_minor: int | None
    computed_amount_minor: int
    explanation: str


class CostEstimateResponse(BaseModel):
    currency: str
    lines: list[CostLineResponse]
    material_subtotal_minor: int
    labor_subtotal_minor: int
    expense_subtotal_minor: int
    real_cost_minor: int
    selling_price_minor: int
    pricing_method: str
    gross_margin_percent: Decimal
    notes: list[str]
