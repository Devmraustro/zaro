"""Payment domain: manual CCP deposit claims with human verification.

ZARO does NOT integrate with any bank/CCP API. A payment row represents a
customer's *claim* that they transferred money; a privileged operator
verifies the uploaded proof manually. The wording everywhere reflects this:
"under review", "confirmed by operator" -- never "verified by CCP".

Financial rules:

- ``amount_minor`` must equal the order's authoritative
  ``deposit_required_minor`` at submission; it can never be edited.
- History is append-oriented: confirm/reject transitions are recorded with
  actor + timestamps; no endpoint mutates amounts or reviewer identity.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PaymentConfiguration(Base, UUIDPrimaryKeyMixin):
    """Singleton row holding the business's CCP payment instructions and the
    default deposit policy.

    Business configuration, not an authentication secret -- but changes are
    restricted (FINANCE_MANAGE) and audited. Payments snapshot the CCP
    context at creation time so later configuration edits never rewrite
    history.
    """

    __tablename__ = "payment_configuration"

    account_holder: Mapped[str] = mapped_column(String(200), nullable=False)
    # CCP card number / postal identifier shown to customers for transfer.
    account_identifier: Mapped[str] = mapped_column(String(120), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    default_deposit_percentage: Mapped[int] = mapped_column(nullable=False, default=40)

    updated_by: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        # At most ONE unresolved claim per order (pending/proof/review) and at
        # most ONE confirmed deposit per order. Rejected/cancelled rows are
        # exempt so resubmission reuses the same record instead of piling up
        # duplicates. (PostgreSQL partial unique indexes; SQLite tests skip
        # them and enforce the invariant in the service layer.)
        Index(
            "uq_payments_order_active",
            "order_id",
            unique=True,
            postgresql_where=text("status IN ('pending','proof_uploaded','under_review')"),
        ),
        Index(
            "uq_payments_order_confirmed",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
    )

    payment_reference: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)

    order_id: Mapped[object] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[object | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    method: Mapped[PaymentMethod] = mapped_column(String(10), nullable=False, default=PaymentMethod.CCP)
    status: Mapped[PaymentStatus] = mapped_column(String(20), nullable=False, default=PaymentStatus.PENDING, index=True)

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Snapshot of the CCP instructions shown to the customer when this
    # payment was created (historical review must not depend on current
    # configuration).
    ccp_account_holder_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    ccp_account_identifier_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)

    rejection_reason_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rejection_reason_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    proof_asset_id: Mapped[object | None] = mapped_column(
        ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True
    )
    proof_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<Payment id={self.id} ref={self.payment_reference!r} status={self.status}>"
