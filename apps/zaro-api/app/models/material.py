from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MaterialCategory, MaterialUnit
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Material(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "materials"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    category: Mapped[MaterialCategory] = mapped_column(String(20), nullable=False)
    unit: Mapped[MaterialUnit] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Material id={self.id} code={self.code!r}>"


class MaterialPrice(Base, UUIDPrimaryKeyMixin):
    """Append-only price history for a material.

    The effective unit price at date D is the row with the greatest
    ``effective_from <= D``. Rows are never mutated or deleted; corrections
    are new rows with later effective dates.
    """

    __tablename__ = "material_prices"
    __table_args__ = (UniqueConstraint("material_id", "effective_from", name="uq_material_prices_material_effective"),)

    material_id: Mapped[object] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")
    created_by: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
