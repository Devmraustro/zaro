"""inventory core: stock levels and movement ledger

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-22

Financial invariants enforced at the database level:

- StockLevel.on_hand >= 0
- StockLevel.reserved >= 0
- StockLevel.reserved <= StockLevel.on_hand
- StockMovement.quantity != 0
- Partial unique index on idempotency_key for idempotency enforcement
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0006"
down_revision: str = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_levels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "material_id",
            sa.Uuid(),
            sa.ForeignKey("materials.id", ondelete="RESTRICT", name="fk_stock_levels_material_id_materials"),
            unique=True,
            nullable=False,
        ),
        sa.Column("on_hand", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("on_hand >= 0", name="ck_stock_levels_on_hand_non_negative"),
        sa.CheckConstraint("reserved >= 0", name="ck_stock_levels_reserved_non_negative"),
        sa.CheckConstraint("reserved <= on_hand", name="ck_stock_levels_reserved_not_exceed_on_hand"),
    )
    op.create_index("ix_stock_levels_material_id", "stock_levels", ["material_id"], unique=True)

    # Use String with CHECK constraint for movement_type (works on both PostgreSQL and SQLite)
    valid_movement_types = (
        "('purchase','reserve','release','consume','production_waste','inventory_waste','adjust','return')"
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "material_id",
            sa.Uuid(),
            sa.ForeignKey("materials.id", ondelete="RESTRICT", name="fk_stock_movements_material_id_materials"),
            nullable=False,
        ),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=True),
        sa.Column("request_fingerprint", sa.LargeBinary(), nullable=True),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column(
            "performed_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_stock_movements_performed_by_users"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity != 0", name="ck_stock_movements_quantity_non_zero"),
        sa.CheckConstraint(f"movement_type IN {valid_movement_types}", name="ck_stock_movements_movement_type_valid"),
    )
    op.create_index("ix_stock_movements_material_id", "stock_movements", ["material_id"])
    op.create_index("ix_stock_movements_material_created", "stock_movements", ["material_id", "created_at"])
    op.create_index("ix_stock_movements_reference", "stock_movements", ["reference_type", "reference_id"])
    op.create_index(
        "uq_stock_movements_idempotency",
        "stock_movements",
        ["idempotency_key"],
        unique=True,
        postgresql_where=text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_stock_movements_idempotency", table_name="stock_movements")
    op.drop_index("ix_stock_movements_reference", table_name="stock_movements")
    op.drop_index("ix_stock_movements_material_created", table_name="stock_movements")
    op.drop_index("ix_stock_movements_material_id", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index("ix_stock_levels_material_id", table_name="stock_levels")
    op.drop_table("stock_levels")
