"""Unit tests for the money abstraction (Phase 2 core requirement)."""

import pytest

from app.core.exceptions import ValidationFailedError
from app.core.money import Currency, Money, format_minor, parse_decimal_to_minor


class TestMoneyConstruction:
    def test_basic_construction(self):
        m = Money(149000)
        assert m.amount_minor == 149000
        assert m.currency == Currency.DZD

    def test_zero_allowed(self):
        assert Money(0).amount_minor == 0

    def test_negative_rejected(self):
        with pytest.raises(ValidationFailedError):
            Money(-1)

    def test_float_rejected(self):
        # Floats must never reach money paths.
        with pytest.raises(ValidationFailedError):
            Money(10.5)  # type: ignore[arg-type]

    def test_bool_rejected(self):
        with pytest.raises(ValidationFailedError):
            Money(True)  # type: ignore[arg-type]

    def test_huge_amount_rejected(self):
        with pytest.raises(ValidationFailedError):
            Money(10**14)


class TestMoneyArithmetic:
    def test_addition(self):
        assert (Money(100) + Money(250)).amount_minor == 350

    def test_subtraction(self):
        assert (Money(500) - Money(200)).amount_minor == 300

    def test_subtraction_below_zero_rejected(self):
        with pytest.raises(ValidationFailedError):
            Money(100) - Money(200)

    def test_currency_mismatch_addition(self):
        # A non-DZD value (e.g. future EUR) must never silently mix.
        other = Money(100, currency="EUR")  # type: ignore[arg-type]
        with pytest.raises(ValidationFailedError):
            _ = other + Money(1)

    def test_multiply_exact(self):
        assert Money(1000).multiply("2.5").amount_minor == 2500

    def test_multiply_rounds_half_up(self):
        # 100.5 minor * 1 -> exact; check a fractional product rounds half-up.
        assert Money(105).multiply("0.5").amount_minor == 53  # 52.5 -> 53

    def test_multiply_negative_factor_rejected(self):
        with pytest.raises(ValidationFailedError):
            Money(100).multiply("-1")

    def test_percentage(self):
        assert Money(20000).percentage("19").amount_minor == 3800

    def test_immutability(self):
        m = Money(100)
        with pytest.raises((AttributeError, TypeError, ValueError)):
            m.amount_minor = 200  # type: ignore[misc]


class TestParsingAndFormatting:
    def test_parse_decimal_string(self):
        assert parse_decimal_to_minor("1490.50") == 149050

    def test_parse_int(self):
        assert parse_decimal_to_minor(20) == 2000

    def test_parse_rounds_half_up(self):
        assert parse_decimal_to_minor("0.005") == 1

    def test_parse_float_string_rejected_as_invalid(self):
        with pytest.raises(ValidationFailedError):
            parse_decimal_to_minor("abc")

    def test_format_minor(self):
        assert format_minor(149000) == "1490.00"

    def test_round_trip(self):
        value = "12345.67"
        assert format_minor(parse_decimal_to_minor(value)) == value


class TestDeterminism:
    def test_repeated_computation_identical(self):
        amounts = [Money(12345).multiply("3.7") for _ in range(50)]
        assert len({a.amount_minor for a in amounts}) == 1
