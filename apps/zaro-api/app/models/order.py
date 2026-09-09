"""Order domain: created server-side from an accepted quote.

An order is a **snapshot** of the accepted quote's commercial terms. Prices
are never recalculated from live product data. ``deposit_required_minor`` is
the authoritative amount every deposit payment must match exactly.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OrderStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal_minor >= 0", name="ck_orders_subtotal_non_negative"),
        CheckConstraint("discount_minor >= 0", name="ck_orders_discount_non_negative"),
        CheckConstraint("delivery_fee_minor >= 0", name="ck_orders_delivery_fee_non_negative"),
        CheckConstraint(
            "total_minor = subtotal_minor - discount_minor + delivery_fee_minor",
            name="ck_orders_total_consistent",
        ),
        CheckConstraint(
            "deposit_paid_minor >= 0 AND deposit_paid_minor <= total_minor",
            name="ck_orders_deposit_paid_bounds",
        ),
        CheckConstraint(
            "balance_due_minor = total_minor - deposit_paid_minor",
            name="ck_orders_balance_consistent",
        ),
        CheckConstraint(
            "deposit_required_minor >= 0 AND deposit_required_minor <= total_minor",
            name="ck_orders_deposit_required_bounds",
        ),
    )

    order_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    customer_id: Mapped[object | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # One order per quote (unique) makes double conversion impossible at the
    # database level, not just in application code.
    quote_id: Mapped[object | None] = mapped_column(
        ForeignKey("quotes.id", ondelete="SET NULL"), unique=True, nullable=True, index=True
    )
    custom_request_id: Mapped[object | None] = mapped_column(
        ForeignKey("custom_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[OrderStatus] = mapped_column(
        String(30), nullable=False, default=OrderStatus.PENDING_DEPOSIT, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")

    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    delivery_fee_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    deposit_required_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deposit_paid_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    balance_due_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Order id={self.id} number={self.order_number!r} status={self.status}>"


class OrderLine(Base, UUIDPrimaryKeyMixin):
    """Frozen copy of a quote line at conversion time."""

    __tablename__ = "order_lines"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_order_lines_quantity_non_negative"),
        CheckConstraint("unit_price_minor >= 0", name="ck_order_lines_unit_price_non_negative"),
        CheckConstraint("line_total_minor >= 0", name="ck_order_lines_total_non_negative"),
    )

    order_id: Mapped[object] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self) -> str:
        return f"<OrderLine order={self.order_id} pos={self.position} {self.line_total_minor}>"
