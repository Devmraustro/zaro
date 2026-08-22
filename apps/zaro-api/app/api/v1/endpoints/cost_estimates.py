"""Cost estimate endpoint (restricted).

Cost breakdowns reveal supplier pricing and margins -- commercially
sensitive data. Access requires ``products.manage_price`` (owner/admin
only). The engine itself is pure; this endpoint is a thin adapter.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.cost_engine import (
    CostLineType,
    ExpenseLineInput,
    LaborLineInput,
    MaterialLineInput,
    PricingMethod,
    PricingPolicy,
    compute_cost,
)
from app.core.exceptions import ValidationFailedError
from app.core.money import Money
from app.db.session import get_db
from app.models.enums import Permission
from app.models.user import User
from app.schemas.cost_engine import CostEstimateRequest

router = APIRouter(prefix="/admin/cost-estimates", tags=["cost-engine"])


def _build_pricing(payload) -> PricingPolicy:
    p = payload.pricing
    if p.method == "target_margin":
        if p.target_margin_percent is None:
            raise ValidationFailedError("target_margin_percent is required for target_margin method")
        return PricingPolicy(PricingMethod.TARGET_MARGIN, p.target_margin_percent)
    if p.method == "markup":
        if p.markup_percent is None:
            raise ValidationFailedError("markup_percent is required for markup method")
        return PricingPolicy(PricingMethod.MARKUP, p.markup_percent)
    if p.manual_selling_price_minor is None:
        raise ValidationFailedError("manual_selling_price_minor is required for manual method")
    return PricingPolicy(PricingMethod.MANUAL, Money(p.manual_selling_price_minor))


@router.post("")
async def create_cost_estimate(
    payload: CostEstimateRequest,
    _user: Annotated[User, Depends(require_permission(Permission.PRODUCTS_MANAGE_PRICE))],
    _db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    material_lines = [
        MaterialLineInput(
            label=m.label,
            quantity=m.quantity,
            unit=m.unit,
            unit_price=Money(m.unit_price_minor),
            waste_percent=m.waste_percent,
        )
        for m in payload.material_lines
    ]
    labor_lines = [
        LaborLineInput(label=ln.label, hours=ln.hours, hourly_rate=Money(ln.hourly_rate_minor))
        for ln in payload.labor_lines
    ]
    expense_lines = [
        ExpenseLineInput(
            label=e.label,
            line_type=CostLineType(e.line_type),
            amount=Money(e.amount_minor) if e.amount_minor is not None else None,
            percent_of_production_cost=e.percent_of_production_cost,
        )
        for e in payload.expense_lines
    ]

    breakdown = compute_cost(
        material_lines=material_lines,
        labor_lines=labor_lines,
        expense_lines=expense_lines,
        pricing=_build_pricing(payload),
    )

    return {
        "currency": "DZD",
        "lines": [
            {
                "line_type": cl.line_type.value,
                "label": cl.label,
                "quantity": str(cl.quantity) if cl.quantity is not None else None,
                "unit": cl.unit,
                "unit_price_minor": cl.unit_price_minor,
                "computed_amount_minor": cl.computed_amount.amount_minor,
                "explanation": cl.explanation,
            }
            for cl in breakdown.lines
        ],
        "material_subtotal_minor": breakdown.material_subtotal.amount_minor,
        "labor_subtotal_minor": breakdown.labor_subtotal.amount_minor,
        "expense_subtotal_minor": breakdown.expense_subtotal.amount_minor,
        "real_cost_minor": breakdown.real_cost.amount_minor,
        "selling_price_minor": breakdown.selling_price.amount_minor,
        "pricing_method": breakdown.pricing_method.value,
        "gross_margin_percent": str(breakdown.gross_margin_percent),
        "notes": list(breakdown.notes),
    }
