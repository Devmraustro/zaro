from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CustomRequestSource, CustomRequestStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CustomRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Customer custom-order request (bespoke furniture inquiry).

    Contact fields are denormalized snapshots: the customer may never have
    an account, and staff need the submission context even if the customer
    record is later merged/cleaned.
    """

    __tablename__ = "custom_requests"

    # Server-controlled reference (CR-2026-0001). Clients can never set it.
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    customer_id: Mapped[object | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    product_type: Mapped[str] = mapped_column(String(50), nullable=False)  # coffee_table, dining_table...
    description: Mapped[str] = mapped_column(Text, nullable=False)
    desired_dimensions: Mapped[str | None] = mapped_column(Text, nullable=True)
    materials: Mapped[str | None] = mapped_column(Text, nullable=True)
    colors: Mapped[str | None] = mapped_column(Text, nullable=True)
    finish: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    budget_min_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    budget_max_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[CustomRequestStatus] = mapped_column(
        String(20), nullable=False, default=CustomRequestStatus.SUBMITTED, index=True
    )
    source: Mapped[CustomRequestSource] = mapped_column(String(20), nullable=False, default=CustomRequestSource.WEBSITE)

    assigned_to: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<CustomRequest id={self.id} ref={self.reference!r} status={self.status}>"
