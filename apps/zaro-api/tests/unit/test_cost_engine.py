"""Unit tests for the deterministic cost engine."""

from decimal import Decimal

import pytest

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


def _material(qty="2", price_minor=50000, waste="0", label="Steel tube"):
    return MaterialLineInput(
        label=label, quantity=qty, unit="meter", unit_price=Money(price_minor), waste_percent=waste
    )


def _labor(hours="3", rate_minor=15000, label="Welding"):
    return LaborLineInput(label=label, hours=hours, hourly_rate=Money(rate_minor))


class TestMaterialLines:
    def test_simple_material_line(self):
        breakdown = compute_cost(
            material_lines=[_material()],
            labor_lines=[],
            expense_lines=[],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(100000)),
        )
        assert breakdown.material_subtotal.amount_minor == 100000  # 2 x 50000
        assert breakdown.real_cost.amount_minor == 100000

    def test_waste_percentage(self):
        breakdown = compute_cost(
            material_lines=[_material(waste="10")],
            labor_lines=[],
            expense_lines=[],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        # 2m * 1.10 * 50000 = 110000
        assert breakdown.material_subtotal.amount_minor == 110000

    def test_zero_price_allowed_and_flagged(self):
        breakdown = compute_cost(
            material_lines=[_material(price_minor=0)],
            labor_lines=[],
            expense_lines=[],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        assert breakdown.real_cost.amount_minor == 0
        assert any("zero-priced" in n for n in breakdown.notes)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationFailedError):
            _material(qty="-1")

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationFailedError):
            _material(qty="0")

    def test_waste_over_100_rejected(self):
        with pytest.raises(ValidationFailedError):
            _material(waste="101")

    def test_fractional_quantities(self):
        breakdown = compute_cost(
            material_lines=[_material(qty="1.5", price_minor=33333)],
            labor_lines=[],
            expense_lines=[],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        # 1.5 * 33333 = 49999.5 -> rounds half-up to 50000
        assert breakdown.material_subtotal.amount_minor == 50000


class TestLaborLines:
    def test_simple_labor_line(self):
        breakdown = compute_cost(
            material_lines=[],
            labor_lines=[_labor()],
            expense_lines=[],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        assert breakdown.labor_subtotal.amount_minor == 45000  # 3h x 15000

    def test_zero_hours_allowed(self):
        breakdown = compute_cost(
            material_lines=[],
            labor_lines=[_labor(hours="0")],
            expense_lines=[],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        assert breakdown.labor_subtotal.amount_minor == 0

    def test_negative_hours_rejected(self):
        with pytest.raises(ValidationFailedError):
            _labor(hours="-2")


class TestExpenseLines:
    def test_flat_expense(self):
        breakdown = compute_cost(
            material_lines=[_material()],
            labor_lines=[_labor()],
            expense_lines=[ExpenseLineInput(label="Screws", line_type=CostLineType.CONSUMABLE, amount=Money(2000))],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        assert breakdown.expense_subtotal.amount_minor == 2000
        assert breakdown.real_cost.amount_minor == 147000  # 100000 + 45000 + 2000

    def test_percent_overhead_of_production(self):
        breakdown = compute_cost(
            material_lines=[_material()],  # 100000
            labor_lines=[_labor()],  # 45000
            expense_lines=[
                ExpenseLineInput(label="Overhead", line_type=CostLineType.OVERHEAD, percent_of_production_cost="20")
            ],
            pricing=PricingPolicy(PricingMethod.MANUAL, Money(0)),
        )
        # 20% of 145000 = 29000
        assert breakdown.expense_subtotal.amount_minor == 29000
        assert breakdown.real_cost.amount_minor == 174000

    def test_both_amount_and_percent_rejected(self):
        with pytest.raises(ValidationFailedError):
            ExpenseLineInput(
                label="Bad",
                line_type=CostLineType.OVERHEAD,
                amount=Money(100),
                percent_of_production_cost="10",
            )

    def test_neither_amount_nor_percent_rejected(self):
        with pytest.raises(ValidationFailedError):
            ExpenseLineInput(label="Bad", line_type=CostLineType.OVERHEAD)


class TestPricing:
    def _breakdown(self, pricing):
        return compute_cost(
            material_lines=[_material()],  # real cost 100000
            labor_lines=[],
            expense_lines=[],
            pricing=pricing,
        )

    def test_target_margin(self):
        b = self._breakdown(PricingPolicy(PricingMethod.TARGET_MARGIN, "20"))
        # cost / (1 - 0.20) = 125000
        assert b.selling_price.amount_minor == 125000
        assert b.gross_margin_percent == Decimal("20.00")

    def test_markup(self):
        b = self._breakdown(PricingPolicy(PricingMethod.MARKUP, "25"))
        # cost * 1.25 = 125000
        assert b.selling_price.amount_minor == 125000

    def test_manual_price(self):
        b = self._breakdown(PricingPolicy(PricingMethod.MANUAL, Money(99999)))
        assert b.selling_price.amount_minor == 99999

    def test_manual_below_cost_flagged(self):
        b = self._breakdown(PricingPolicy(PricingMethod.MANUAL, Money(50000)))
        assert any("below real cost" in n for n in b.notes)

    def test_margin_100_rejected(self):
        with pytest.raises(ValidationFailedError):
            PricingPolicy(PricingMethod.TARGET_MARGIN, "100")

    def test_negative_margin_rejected(self):
        with pytest.raises(ValidationFailedError):
            PricingPolicy(PricingMethod.TARGET_MARGIN, "-5")

    def test_zero_margin_sells_at_cost(self):
        b = self._breakdown(PricingPolicy(PricingMethod.TARGET_MARGIN, "0"))
        assert b.selling_price.amount_minor == 100000


class TestDeterminismAndBoundaries:
    def full_breakdown(self):
        return compute_cost(
            material_lines=[_material(), _material(qty="1.25", price_minor=1234567, waste="7.5")],
            labor_lines=[_labor(), _labor(hours="0.5", rate_minor=9900, label="Finishing")],
            expense_lines=[
                ExpenseLineInput(label="Consumables", line_type=CostLineType.CONSUMABLE, amount=Money(17500)),
                ExpenseLineInput(label="Overhead", line_type=CostLineType.OVERHEAD, percent_of_production_cost="12"),
            ],
            pricing=PricingPolicy(PricingMethod.TARGET_MARGIN, "30"),
        )

    def test_deterministic_across_runs(self):
        first = self.full_breakdown()
        for _ in range(20):
            again = self.full_breakdown()
            assert again.real_cost == first.real_cost
            assert again.selling_price == first.selling_price
            assert [ln.computed_amount for ln in again.lines] == [ln.computed_amount for ln in first.lines]

    def test_explanations_present_for_every_line(self):
        b = self.full_breakdown()
        assert all(line.explanation for line in b.lines)
        assert len(b.lines) == 6

    def test_huge_values_rejected(self):
        with pytest.raises(ValidationFailedError):
            _material(qty="2000000")
        with pytest.raises(ValidationFailedError):
            _labor(hours="200000")
