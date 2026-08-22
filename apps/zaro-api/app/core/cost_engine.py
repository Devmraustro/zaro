"""Deterministic product cost engine.

Phase 2 core requirement. The engine computes a fully-auditable cost
breakdown from material, labor and expense lines, then derives a selling
price from an explicit pricing policy.

Design rules:

- **Integer money only.** All amounts are ``Money`` values in minor units.
  Quantities/hours/percentages are ``Decimal`` (exact), never float.
- **Determinism.** Identical inputs always produce identical outputs.
  Rounding is ROUND_HALF_UP to the nearest minor unit, applied once per
  line and once at pricing -- never iteratively.
- **Purity.** No I/O, no clocks, no randomness. The caller resolves
  historical material prices and passes them in.
- **Validation.** Negative quantities/rates are rejected; zero unit prices
  are allowed (donated/scrap materials exist) but flagged in the breakdown.
  Magnitudes are bounded to catch input abuse.

Formula reference (all in major currency units)::

    material_line = quantity * unit_price * (1 + waste_pct / 100)
    labor_line    = hours * hourly_rate
    expense_line  = flat amount | pct * (materials + labor)
    real_cost     = sum(all lines)
    selling_price = real_cost / (1 - margin_pct)      # target margin
                  | real_cost * (1 + markup_pct)      # markup
                  | explicit target price             # manual override
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from enum import StrEnum

from app.core.exceptions import ValidationFailedError
from app.core.money import Currency, Money

# Magnitude bounds (defense against absurd inputs; far above real use).
MAX_QUANTITY = Decimal("1000000")
MAX_HOURS = Decimal("100000")
MAX_PERCENT = Decimal("1000")


def _to_decimal(value: str | int | Decimal, field_name: str) -> Decimal:
    if isinstance(value, bool | float):
        raise ValidationFailedError(f"{field_name} must be a string or integer decimal, not float")
    try:
        dec = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationFailedError(f"{field_name} is not a valid decimal") from exc
    if not dec.is_finite():
        raise ValidationFailedError(f"{field_name} must be finite")
    return dec


def _validate_positive_decimal(
    value: str | int | Decimal, field_name: str, maximum: Decimal, *, allow_zero: bool = False
) -> Decimal:
    dec = _to_decimal(value, field_name)
    if dec < 0 or (dec == 0 and not allow_zero):
        raise ValidationFailedError(f"{field_name} must be greater than zero")
    if dec > maximum:
        raise ValidationFailedError(f"{field_name} exceeds the maximum supported value ({maximum})")
    return dec


def _validate_percent(value: str | int | Decimal, field_name: str, *, maximum: Decimal = MAX_PERCENT) -> Decimal:
    dec = _to_decimal(value, field_name)
    if dec < 0 or dec > maximum:
        raise ValidationFailedError(f"{field_name} must be between 0 and {maximum}")
    return dec


class CostLineType(StrEnum):
    MATERIAL = "material"
    LABOR = "labor"
    CONSUMABLE = "consumable"
    OVERHEAD = "overhead"
    PACKAGING = "packaging"


class PricingMethod(StrEnum):
    TARGET_MARGIN = "target_margin"
    MARKUP = "markup"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class MaterialLineInput:
    """One bill-of-materials row."""

    label: str
    quantity: str | int | Decimal
    unit: str
    unit_price: Money
    waste_percent: str | int | Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValidationFailedError("material line label is required")
        _validate_positive_decimal(self.quantity, "quantity", MAX_QUANTITY)
        _validate_percent(self.waste_percent, "waste_percent", maximum=Decimal("100"))


@dataclass(frozen=True, slots=True)
class LaborLineInput:
    """One labor row (hours at an hourly rate)."""

    label: str
    hours: str | int | Decimal
    hourly_rate: Money

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValidationFailedError("labor line label is required")
        _validate_positive_decimal(self.hours, "hours", MAX_HOURS, allow_zero=True)


@dataclass(frozen=True, slots=True)
class ExpenseLineInput:
    """Flat expense (consumables, packaging) or percentage overhead."""

    label: str
    line_type: CostLineType  # CONSUMABLE, OVERHEAD or PACKAGING
    amount: Money | None = None
    percent_of_production_cost: str | int | Decimal | None = None

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValidationFailedError("expense line label is required")
        if self.line_type not in (CostLineType.CONSUMABLE, CostLineType.OVERHEAD, CostLineType.PACKAGING):
            raise ValidationFailedError("expense line type must be consumable, overhead or packaging")
        if (self.amount is None) == (self.percent_of_production_cost is None):
            raise ValidationFailedError("expense line must have exactly one of amount or percent_of_production_cost")
        if self.amount is not None and self.amount.amount_minor < 0:
            raise ValidationFailedError("expense amount must not be negative")
        if self.percent_of_production_cost is not None:
            _validate_percent(self.percent_of_production_cost, "percent_of_production_cost")


@dataclass(frozen=True, slots=True)
class PricingPolicy:
    """How the selling price is derived from the real cost."""

    method: PricingMethod
    # For TARGET_MARGIN: percent of selling price that is profit (0..99).
    # For MARKUP: percent added on top of cost (0..MAX_PERCENT).
    # For MANUAL: the explicit selling price.
    value: Money | str | int | Decimal | None = None

    def __post_init__(self) -> None:
        if self.method == PricingMethod.TARGET_MARGIN:
            pct = _validate_percent(self.value, "target_margin_percent")  # type: ignore[arg-type]
            if pct >= 100:
                raise ValidationFailedError("target_margin_percent must be below 100")
        elif self.method == PricingMethod.MARKUP:
            _validate_percent(self.value, "markup_percent")  # type: ignore[arg-type]
        elif self.method == PricingMethod.MANUAL:
            if not isinstance(self.value, Money):
                raise ValidationFailedError("manual pricing requires a Money value")
        else:
            raise ValidationFailedError("unknown pricing method")


@dataclass(frozen=True, slots=True)
class CostLine:
    line_type: CostLineType
    label: str
    quantity: Decimal | None
    unit: str | None
    unit_price_minor: int | None
    computed_amount: Money
    explanation: str


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    currency: Currency
    lines: tuple[CostLine, ...]
    material_subtotal: Money
    labor_subtotal: Money
    expense_subtotal: Money
    real_cost: Money
    selling_price: Money
    pricing_method: PricingMethod
    gross_margin_percent: Decimal
    notes: tuple[str, ...] = field(default=())


def compute_material_line(line: MaterialLineInput) -> CostLine:
    quantity = _to_decimal(line.quantity, "quantity")
    gross_quantity = quantity * (Decimal(1) + _to_decimal(line.waste_percent, "waste_percent") / Decimal(100))
    amount = line.unit_price.multiply(gross_quantity)
    explanation = f"{quantity} {line.unit} x {line.unit_price.amount_minor} minor" + (
        f" incl. {line.waste_percent}% waste" if line.waste_percent else ""
    )
    if line.unit_price.amount_minor == 0:
        explanation += " (zero-price line)"
    return CostLine(
        CostLineType.MATERIAL,
        line.label.strip(),
        quantity,
        line.unit,
        line.unit_price.amount_minor,
        amount,
        explanation,
    )


def compute_labor_line(line: LaborLineInput) -> CostLine:
    hours = _to_decimal(line.hours, "hours")
    amount = line.hourly_rate.multiply(hours)
    return CostLine(
        CostLineType.LABOR,
        line.label.strip(),
        hours,
        "hour",
        line.hourly_rate.amount_minor,
        amount,
        f"{hours} h x {line.hourly_rate.amount_minor} minor/h",
    )


def compute_expense_line(line: ExpenseLineInput, production_subtotal: Money) -> CostLine:
    if line.amount is not None:
        amount = line.amount
        explanation = "flat amount"
    else:
        assert line.percent_of_production_cost is not None  # validated in __post_init__
        pct = _to_decimal(line.percent_of_production_cost, "percent_of_production_cost")
        amount = production_subtotal.percentage(pct)
        explanation = f"{pct}% of production subtotal ({production_subtotal.amount_minor} minor)"
    return CostLine(line.line_type, line.label.strip(), None, None, None, amount, explanation)


def compute_cost(
    *,
    material_lines: list[MaterialLineInput],
    labor_lines: list[LaborLineInput],
    expense_lines: list[ExpenseLineInput],
    pricing: PricingPolicy,
) -> CostBreakdown:
    """Compute the full cost breakdown and selling price.

    Raises :class:`ValidationFailedError` on any invalid input; callers get
    a single deterministic result otherwise.
    """
    currency = Currency.DZD
    for mline in material_lines:
        if mline.unit_price.currency != currency:
            raise ValidationFailedError("All lines must use DZD")
    for lline in labor_lines:
        if lline.hourly_rate.currency != currency:
            raise ValidationFailedError("All lines must use DZD")
    for eline in expense_lines:
        if eline.amount is not None and eline.amount.currency != currency:
            raise ValidationFailedError("All lines must use DZD")

    computed: list[CostLine] = [compute_material_line(m) for m in material_lines]
    computed += [compute_labor_line(ln) for ln in labor_lines]

    material_subtotal = Money.zero(currency)
    labor_subtotal = Money.zero(currency)
    for cl in computed:
        if cl.line_type == CostLineType.MATERIAL:
            material_subtotal += cl.computed_amount
        elif cl.line_type == CostLineType.LABOR:
            labor_subtotal += cl.computed_amount

    production_subtotal = material_subtotal + labor_subtotal
    expense_subtotal = Money.zero(currency)
    for el in expense_lines:
        cl = compute_expense_line(el, production_subtotal)
        computed.append(cl)
        expense_subtotal += cl.computed_amount

    real_cost = production_subtotal + expense_subtotal

    notes: list[str] = []
    zero_price_lines = [cl.label for cl in computed if cl.unit_price_minor == 0]
    if zero_price_lines:
        notes.append("zero-priced lines present: " + ", ".join(zero_price_lines))

    if pricing.method == PricingMethod.TARGET_MARGIN:
        assert isinstance(pricing.value, (str, int, Decimal))
        margin_pct = _to_decimal(pricing.value, "target_margin_percent")
        divisor = Decimal(1) - margin_pct / Decimal(100)
        with localcontext() as ctx:
            ctx.prec = 28
            selling_minor = int(
                (Decimal(real_cost.amount_minor) / divisor).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            )
        selling_price = Money(selling_minor, currency)
    elif pricing.method == PricingMethod.MARKUP:
        assert isinstance(pricing.value, (str, int, Decimal))
        markup_pct = _to_decimal(pricing.value, "markup_percent")
        selling_price = real_cost.multiply(Decimal(1) + markup_pct / Decimal(100))
    else:
        assert isinstance(pricing.value, Money)
        selling_price = pricing.value
        if selling_price < real_cost:
            notes.append("manual price is below real cost (negative margin)")

    gross_margin = (
        (Decimal(selling_price.amount_minor - real_cost.amount_minor) / Decimal(selling_price.amount_minor) * 100)
        if selling_price.amount_minor > 0
        else Decimal(0)
    ).quantize(Decimal("0.01"))

    return CostBreakdown(
        currency=currency,
        lines=tuple(computed),
        material_subtotal=material_subtotal,
        labor_subtotal=labor_subtotal,
        expense_subtotal=expense_subtotal,
        real_cost=real_cost,
        selling_price=selling_price,
        pricing_method=pricing.method,
        gross_margin_percent=gross_margin,
        notes=tuple(notes),
    )
