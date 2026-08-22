"""Quote domain: commercial offer with an immutable price snapshot.

Financial rules:

- All amounts are integer minor units (centimes) with an explicit currency.
- Totals and the deposit are computed **server-side**; a quote row is a
  frozen snapshot of the terms presented to the customer. Later product or
  policy changes never mutate issued quotes.
- ``deposit_percentage`` records the policy actually applied to THIS quote
  so historical quotes stay reproducible when the default changes.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import QuoteStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Quote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint("subtotal_minor >= 0", name="ck_quotes_subtotal_non_negative"),
        CheckConstraint("discount_minor >= 0", name="ck_quotes_discount_non_negative"),
        CheckConstraint("delivery_fee_minor >= 0", name="ck_quotes_delivery_fee_non_negative"),
        CheckConstraint(
            "total_minor = subtotal_minor - discount_minor + delivery_fee_minor",
            name="ck_quotes_total_consistent",
        ),
        CheckConstraint(
            "deposit_amount_minor >= 0 AND deposit_amount_minor <= total_minor",
            name="ck_quotes_deposit_bounds",
        ),
        CheckConstraint("balance_amount_minor >= 0", name="ck_quotes_balance_non_negative"),
        CheckConstraint(
            "deposit_percentage >= 0 AND deposit_percentage <= 100",
            name="ck_quotes_deposit_percentage_bounds",
        ),
    )

    # Server-controlled human reference (ZQ-2026-000001). Never an auth token.
    quote_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    customer_id: Mapped[object | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    custom_request_id: Mapped[object | None] = mapped_column(
        ForeignKey("custom_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[QuoteStatus] = mapped_column(String(20), nullable=False, default=QuoteStatus.DRAFT, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")

    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    delivery_fee_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    deposit_percentage: Mapped[int] = mapped_column(nullable=False, default=40)
    deposit_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # internal staff notes

    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_by: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Quote id={self.id} number={self.quote_number!r} status={self.status}>"


class QuoteLine(Base, UUIDPrimaryKeyMixin):
    """One priced line of the quote snapshot.

    Lines are immutable once the quote leaves DRAFT: they preserve exactly
    what the customer was shown (description, quantity, unit price).
    """

    __tablename__ = "quote_lines"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_quote_lines_quantity_non_negative"),
        CheckConstraint("unit_price_minor >= 0", name="ck_quote_lines_unit_price_non_negative"),
        CheckConstraint("line_total_minor >= 0", name="ck_quote_lines_total_non_negative"),
    )

    quote_id: Mapped[object] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_label: Mapped[str | None] = mapped_column(String(30), nullable=True)  # e.g. "piece", "m"
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self) -> str:
        return f"<QuoteLine quote={self.quote_id} pos={self.position} {self.line_total_minor}>"
