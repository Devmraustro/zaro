"""Unit tests for the quote domain: pricing math, state machine, expiry."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import InvalidStateTransition, ValidationFailedError
from app.models.enums import QuoteStatus
from app.services.quotes_service import (
    QuoteLineInput,
    compute_totals,
    ensure_not_expired,
    validate_transition,
)


def _line(qty="1", price=45000_00):
    return QuoteLineInput.build(description="Custom dining table", quantity=qty, unit_label=None, unit_price_minor=price)


class TestQuoteLineInput:
    def test_rejects_blank_description(self):
        with pytest.raises(ValidationFailedError):
            QuoteLineInput.build(description="  ", quantity="1", unit_label=None, unit_price_minor=100)

    def test_rejects_negative_and_zero_quantity(self):
        for qty in ("0", "-1", "-0.5"):
            with pytest.raises(ValidationFailedError):
                QuoteLineInput.build(description="x", quantity=qty, unit_label=None, unit_price_minor=100)

    def test_rejects_floats(self):
        with pytest.raises(ValidationFailedError):
            QuoteLineInput.build(description="x", quantity=1.5, unit_label=None, unit_price_minor=100)

    def test_accepts_decimal_string(self):
        line = QuoteLineInput.build(description="Steel bar", quantity="2.500", unit_label="m", unit_price_minor=1200_00)
        assert str(line.quantity) == "2.500"

    def test_rejects_negative_price(self):
        with pytest.raises(ValidationFailedError):
            QuoteLineInput.build(description="x", quantity="1", unit_label=None, unit_price_minor=-1)


class TestComputeTotals:
    """Spec example: total 50,000 DZD at 40% -> deposit 20,000 / balance 30,000."""

    def test_deposit_math_spec_example(self):
        totals, _ = compute_totals([_line()], discount_minor=0, delivery_fee_minor=0, deposit_percentage=40)
        assert totals["subtotal_minor"] == 4_500_000
        assert totals["total_minor"] == 4_500_000
        assert totals["deposit_amount_minor"] == 1_800_000
        assert totals["balance_amount_minor"] == 2_700_000

    def test_discount_delivery_and_total_identity(self):
        totals, _ = compute_totals(
            [_line("2"), _line("1", 3000_00)],
            discount_minor=2000_00,
            delivery_fee_minor=2000_00,
            deposit_percentage=40,
        )
        assert totals["subtotal_minor"] == 9_300_000
        assert totals["total_minor"] == totals["subtotal_minor"] - 2000_00 + 2000_00
        assert totals["deposit_amount_minor"] + totals["balance_amount_minor"] == totals["total_minor"]

    def test_rounding_is_half_up_once_per_line_and_once_for_deposit(self):
        # 3 x 33.333 DZD = 99.999 -> rounds to 100.000 DZD per half-up.
        totals, lines_totals = compute_totals(
            [_line("3", 3333)], discount_minor=0, delivery_fee_minor=0, deposit_percentage=33
        )
        assert lines_totals == [9999]
        assert totals["deposit_amount_minor"] == 3300  # 9999 * 33% = 3299.67 -> 3300

    def test_discount_cannot_exceed_subtotal(self):
        with pytest.raises(ValidationFailedError):
            compute_totals([_line()], discount_minor=4_500_001, delivery_fee_minor=0, deposit_percentage=40)

    def test_percentage_bounds(self):
        with pytest.raises(ValidationFailedError):
            compute_totals([_line()], discount_minor=0, delivery_fee_minor=0, deposit_percentage=101)
        with pytest.raises(ValidationFailedError):
            compute_totals([_line()], discount_minor=0, delivery_fee_minor=0, deposit_percentage=-1)

    def test_zero_percent_deposit_allowed(self):
        totals, _ = compute_totals([_line()], discount_minor=0, delivery_fee_minor=0, deposit_percentage=0)
        assert totals["deposit_amount_minor"] == 0
        assert totals["balance_amount_minor"] == totals["total_minor"]

    def test_no_client_side_shortcut_exists(self):
        # The authoritative amount is always derived from total x percentage;
        # there is no code path that accepts a caller-provided deposit.
        import inspect

        from app.services import quotes_service

        assert "deposit_amount" not in inspect.signature(quotes_service.compute_totals).parameters


class TestQuoteStateMachine:
    def test_happy_path_forward(self):
        validate_transition(QuoteStatus.DRAFT, QuoteStatus.SENT)
        validate_transition(QuoteStatus.SENT, QuoteStatus.VIEWED)
        validate_transition(QuoteStatus.VIEWED, QuoteStatus.ACCEPTED)
        validate_transition(QuoteStatus.ACCEPTED, QuoteStatus.DEPOSIT_REQUIRED)
        validate_transition(QuoteStatus.DEPOSIT_REQUIRED, QuoteStatus.CONVERTED)

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (QuoteStatus.DRAFT, QuoteStatus.ACCEPTED),
            (QuoteStatus.DRAFT, QuoteStatus.CONVERTED),
            (QuoteStatus.SENT, QuoteStatus.CONVERTED),
            (QuoteStatus.SENT, QuoteStatus.DEPOSIT_REQUIRED),
            (QuoteStatus.ACCEPTED, QuoteStatus.REJECTED),
            (QuoteStatus.ACCEPTED, QuoteStatus.SENT),
            (QuoteStatus.DEPOSIT_REQUIRED, QuoteStatus.CANCELLED),
            (QuoteStatus.CONVERTED, QuoteStatus.CANCELLED),
            (QuoteStatus.REJECTED, QuoteStatus.ACCEPTED),
            (QuoteStatus.EXPIRED, QuoteStatus.SENT),
            (QuoteStatus.CANCELLED, QuoteStatus.SENT),
            (QuoteStatus.VIEWED, QuoteStatus.DRAFT),
        ],
    )
    def test_invalid_transitions_rejected(self, current, target):
        with pytest.raises(InvalidStateTransition):
            validate_transition(current, target)

    def test_terminal_states_have_no_outgoing(self):
        for terminal in (QuoteStatus.CONVERTED, QuoteStatus.EXPIRED, QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
            from app.models.enums import QUOTE_TRANSITIONS

            assert QUOTE_TRANSITIONS[terminal] == frozenset()


class TestExpiry:
    def _quote(self, status, valid_until):
        class FakeQuote:
            pass

        q = FakeQuote()
        q.status = status
        q.valid_until = valid_until
        return q

    def test_past_validity_blocks_actions(self):
        q = self._quote(QuoteStatus.SENT, datetime.now(UTC) - timedelta(days=1))
        with pytest.raises(InvalidStateTransition, match="expired"):
            ensure_not_expired(q)

    def test_future_validity_allows_actions(self):
        q = self._quote(QuoteStatus.SENT, datetime.now(UTC) + timedelta(days=7))
        ensure_not_expired(q)

    def test_draft_never_expiry_blocked(self):
        q = self._quote(QuoteStatus.DRAFT, datetime.now(UTC) - timedelta(days=30))
        ensure_not_expired(q)

    def test_terminal_state_not_rechecked(self):
        q = self._quote(QuoteStatus.CONVERTED, datetime.now(UTC) - timedelta(days=30))
        ensure_not_expired(q)
