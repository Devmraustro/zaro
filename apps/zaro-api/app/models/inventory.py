"""Inventory domain: material stock levels and immutable movement ledger.

Design:

- StockLevel is the transactional materialized balance per material.
- StockMovement is the immutable append-only audit ledger.
- All mutations go through InventoryService; no direct writes allowed.
- Idempotency keys prevent duplicate mutations from retries.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import StockMovementType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class StockLevel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Current stock balance for a material.

    Single source of truth for on-hand and reserved quantities.
    Only InventoryService may mutate these columns.
    """

    __tablename__ = "stock_levels"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="ck_stock_levels_on_hand_non_negative"),
        CheckConstraint("reserved >= 0", name="ck_stock_levels_reserved_non_negative"),
        CheckConstraint("reserved <= on_hand", name="ck_stock_levels_reserved_not_exceed_on_hand"),
    )

    material_id: Mapped[UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True
    )
    on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    reserved: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))

    def available(self) -> Decimal:
        """Compute available quantity (not stored)."""
        return self.on_hand - self.reserved

    def __repr__(self) -> str:
        return f"<StockLevel material={self.material_id} on_hand={self.on_hand} reserved={self.reserved}>"


class StockMovement(Base, UUIDPrimaryKeyMixin):
    """Immutable record of a single stock mutation.

    Append-only ledger; never modified after insert.
    Idempotency key prevents duplicate mutations from retries.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity != 0", name="ck_stock_movements_quantity_non_zero"),
        Index("ix_stock_movements_material_created", "material_id", "created_at"),
        Index(
            "uq_stock_movements_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    material_id: Mapped[UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type: Mapped[StockMovementType] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[UUID | None] = mapped_column(nullable=True)
    idempotency_key: Mapped[UUID | None] = mapped_column(nullable=True)
    request_fingerprint: Mapped[bytes | None] = mapped_column(nullable=True)
    unit_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")
    performed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<StockMovement id={self.id} material={self.material_id} type={self.movement_type} qty={self.quantity}>"
