from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CustomerStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """External customer record.

    Customers may exist without a user account (Instagram/phone orders);
    ``user_id`` links an account when one exists (V2 self-service portal).
    """

    __tablename__ = "customers"

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # internal staff notes
    status: Mapped[CustomerStatus] = mapped_column(String(20), nullable=False, default=CustomerStatus.ACTIVE)
    user_id: Mapped[object | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.full_name!r}>"
