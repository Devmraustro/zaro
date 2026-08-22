"""Money representation for ZARO.

Design decisions (Phase 2):

- Monetary amounts are stored and transported as **integer minor units**
  (centimes for DZD). Floats are never used for money anywhere in the
  codebase; every arithmetic operation happens on ints or ``Decimal`` and
  results are rounded deterministically (ROUND_HALF_UP) back to minor units.
- Currency is an explicit ISO-4217 code carried alongside every amount.
  DZD is the initial business currency but nothing hardcodes it outside
  this module's registry.
- ``Money`` is an immutable value object; operations between currencies
  raise rather than silently converting.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from enum import StrEnum

from app.core.exceptions import ValidationFailedError

# Deterministic arithmetic context: library code must not depend on the
# process-global decimal context, which any other module could mutate.
_DECIMAL_PRECISION = 28


class Currency(StrEnum):
    DZD = "DZD"


# Minor units per currency unit (exponent of ISO-4217).
MINOR_UNITS: dict[Currency, int] = {
    Currency.DZD: 2,
}

# Sanity ceiling: 10^13 minor units = 100 billion DZD. Anything larger is a
# bug or an attack, not a price.
MAX_AMOUNT_MINOR = 10**13


def validate_amount_minor(amount: int, *, field: str = "amount", allow_zero: bool = True) -> int:
    """Validate a raw integer minor-unit amount arriving from any boundary."""
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise ValidationFailedError(f"{field} must be an integer amount in minor units")
    if amount > MAX_AMOUNT_MINOR:
        raise ValidationFailedError(f"{field} exceeds the maximum supported value")
    if amount < 0:
        raise ValidationFailedError(f"{field} must not be negative")
    if amount == 0 and not allow_zero:
        raise ValidationFailedError(f"{field} must be greater than zero")
    return amount


def parse_decimal_to_minor(value: str | int | Decimal, currency: Currency = Currency.DZD) -> int:
    """Convert a human decimal string (e.g. \"1490.50\") into minor units.

    Accepts str/int/Decimal; rejects floats at the type level because float
    literals cannot represent decimal fractions exactly.
    """
    exponent = MINOR_UNITS[currency]
    quantum = Decimal(1).scaleb(-exponent)
    try:
        dec = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationFailedError("Invalid monetary value") from exc
    if not dec.is_finite():
        raise ValidationFailedError("Invalid monetary value")
    rounded = dec.quantize(quantum, rounding=ROUND_HALF_UP)
    minor = int(rounded.scaleb(exponent))
    return validate_amount_minor(minor)


def format_minor(amount_minor: int, currency: Currency = Currency.DZD) -> str:
    """Render minor units as a canonical decimal string (for APIs/UIs)."""
    validate_amount_minor(amount_minor)
    exponent = MINOR_UNITS[currency]
    return str(Decimal(amount_minor).scaleb(-exponent).quantize(Decimal(1).scaleb(-exponent)))


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary value in minor units."""

    amount_minor: int
    currency: Currency = Currency.DZD

    def __post_init__(self) -> None:
        validate_amount_minor(self.amount_minor)

    # -- construction ---------------------------------------------------------

    @classmethod
    def from_major(cls, value: str | int | Decimal, currency: Currency = Currency.DZD) -> Money:
        return cls(parse_decimal_to_minor(value, currency), currency)

    @classmethod
    def zero(cls, currency: Currency = Currency.DZD) -> Money:
        return cls(0, currency)

    # -- arithmetic -----------------------------------------------------------

    def _require_same_currency(self, other: Money) -> None:
        self_currency = getattr(self.currency, "value", str(self.currency))
        other_currency = getattr(other.currency, "value", str(other.currency))
        if other_currency != self_currency:
            raise ValidationFailedError(f"Cannot operate on {self_currency} and {other_currency} amounts")

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        result = self.amount_minor + other.amount_minor
        validate_amount_minor(result)
        return Money(result, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        result = self.amount_minor - other.amount_minor
        if result < 0:
            raise ValidationFailedError("Monetary subtraction would produce a negative amount")
        return Money(result, self.currency)

    def multiply(self, factor: str | int | Decimal) -> Money:
        """Scale by a non-negative Decimal factor with deterministic rounding."""
        try:
            dec = Decimal(str(factor))
        except InvalidOperation as exc:
            raise ValidationFailedError("Invalid multiplication factor") from exc
        if not dec.is_finite() or dec < 0:
            raise ValidationFailedError("Multiplication factor must be a finite non-negative value")
        with localcontext() as ctx:
            ctx.prec = _DECIMAL_PRECISION
            product = (Decimal(self.amount_minor) * dec).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return Money(validate_amount_minor(int(product)), self.currency)

    def percentage(self, percent: str | int | Decimal) -> Money:
        """Return percent% of this amount (deterministic, half-up rounding)."""
        with localcontext() as ctx:
            ctx.prec = _DECIMAL_PRECISION
            factor = Decimal(str(percent)) / Decimal(100)
        return self.multiply(factor)

    # -- comparison -----------------------------------------------------------

    def __lt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount_minor < other.amount_minor

    def __le__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount_minor <= other.amount_minor

    def __gt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount_minor > other.amount_minor

    def __ge__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount_minor >= other.amount_minor
