"""Production domain: production orders and material reservations.

Phase 4 MVP constraint: one ProductionOrder per Order.
This is an operational layer -- financial totals (quote/order totals, deposits, balance)
are NEVER modified by production operations.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProductionOrderStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProductionOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Production order created from a confirmed order.

    MVP constraint: one ProductionOrder per Order (enforced by unique FK).
    Financial invariants: production operations NEVER modify order/quote totals,
    deposits, or balance due.
    """

    __tablename__ = "production_orders"
    __table_args__ = (
        CheckConstraint(
            "estimated_material_cost_minor >= 0",
            name="ck_production_orders_est_material_cost_non_negative",
        ),
        CheckConstraint(
            "actual_material_cost_minor >= 0",
            name="ck_production_orders_actual_material_cost_non_negative",
        ),
    )

    # Server-controlled human reference (ZPROD-2026-000001). Never an auth token.
    production_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    # Links (exactly one order per production order in MVP)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    custom_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("custom_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[ProductionOrderStatus] = mapped_column(
        String(30), nullable=False, default=ProductionOrderStatus.PENDING, index=True
    )

    # Cost tracking (internal operational metrics only -- NEVER modify financial order totals)
    estimated_material_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    actual_material_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Scheduling
    planned_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assignment
    assigned_worker_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supervisor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    qc_inspector_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # State timestamps
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    materials_reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    production_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_check_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_check_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # QC
    qc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    qc_defects: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    material_reservations: Mapped[list["ProductionMaterialReservation"]] = relationship(
        back_populates="production_order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProductionOrder id={self.id} number={self.production_number!r} status={self.status}>"


class ProductionMaterialReservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable snapshot of a material requirement for a production order.

    Snapshot taken at planning time. Later changes to Material, MaterialPrice, or Product
    must NOT mutate existing ProductionOrder material requirements.

    Tracks the lifecycle of a material reservation from planning through consumption.
    """

    __tablename__ = "production_material_reservations"
    __table_args__ = (
        CheckConstraint("quantity_required >= 0", name="ck_prod_mat_res_qty_required_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="ck_prod_mat_res_qty_reserved_non_negative"),
        CheckConstraint("quantity_consumed >= 0", name="ck_prod_mat_res_qty_consumed_non_negative"),
        CheckConstraint("quantity_wasted >= 0", name="ck_prod_mat_res_qty_wasted_non_negative"),
        CheckConstraint("quantity_returned >= 0", name="ck_prod_mat_res_qty_returned_non_negative"),
        CheckConstraint("quantity_released >= 0", name="ck_prod_mat_res_qty_released_non_negative"),
        CheckConstraint(
            "quantity_consumed + quantity_wasted + quantity_returned + quantity_released <= quantity_reserved",
            name="ck_prod_mat_res_remaining_reserved_non_negative",
        ),
    )

    production_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Immutable snapshot fields (set at planning time, never change)
    material_name: Mapped[str] = mapped_column(String(120), nullable=False)
    material_code: Mapped[str] = mapped_column(String(40), nullable=False)
    material_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    material_spec: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Mutable tracking fields
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_consumed: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_wasted: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_returned: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_released: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)

    # Timestamps for tracking
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fully_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    production_order: Mapped["ProductionOrder"] = relationship(back_populates="material_reservations")

    @property
    def remaining_reserved(self) -> Decimal:
        """Compute remaining reserved quantity available for consumption."""
        return (
            self.quantity_reserved
            - self.quantity_consumed
            - self.quantity_wasted
            - self.quantity_returned
            - self.quantity_released
        )

    def __repr__(self) -> str:
        return f"ProdRes(prod={self.production_order_id}, mat={self.material_id}, status={self.status})"
