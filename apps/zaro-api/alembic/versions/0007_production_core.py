"""phase 4 production core: production orders and material reservations

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-23

Production core tables:

- production_orders: one per Order (MVP constraint: 1:1)
- production_material_reservations: immutable BOM snapshots with consumption tracking

Financial invariants enforced at the database level:

- ProductionOrder never modifies Order/Quote financial totals
- ProductionMaterialReservation tracks consumption with CHECK constraints
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0007"
down_revision: str = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == "postgresql"

    if is_postgresql:
        # Create ProductionOrderStatus enum (PostgreSQL only)
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'productionorderstatus') THEN
                    CREATE TYPE productionorderstatus AS ENUM (
                        'pending',
                        'planned',
                        'materials_reserved',
                        'in_production',
                        'paused',
                        'quality_check',
                        'ready',
                        'completed',
                        'cancelled'
                    );
                END IF;
            END $$;
        """)

        # Create ProductionMaterialReservationStatus enum (PostgreSQL only)
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'productionmaterialreservationstatus') THEN
                    CREATE TYPE productionmaterialreservationstatus AS ENUM (
                        'pending',
                        'reserved',
                        'released',
                        'consumed',
                        'cancelled'
                    );
                END IF;
            END $$;
        """)

    # Production Orders table
    op.create_table(
        "production_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("production_number", sa.String(20), nullable=False),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT", name="fk_production_orders_order_id_orders"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_production_orders_customer_id_customers"),
            nullable=True,
        ),
        sa.Column(
            "custom_request_id",
            sa.Uuid(),
            sa.ForeignKey(
                "custom_requests.id", ondelete="SET NULL", name="fk_production_orders_custom_request_id_custom_requests"
            ),
            nullable=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("estimated_material_cost_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("actual_material_cost_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("planned_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "assigned_worker_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_production_orders_assigned_worker_id_users"),
            nullable=True,
        ),
        sa.Column(
            "supervisor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_production_orders_supervisor_id_users"),
            nullable=True,
        ),
        sa.Column(
            "qc_inspector_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_production_orders_qc_inspector_id_users"),
            nullable=True,
        ),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("materials_reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("production_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality_check_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality_check_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("qc_notes", sa.Text(), nullable=True),
        sa.Column("qc_defects", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estimated_material_cost_minor >= 0",
            name="ck_production_orders_est_material_cost_non_negative",
        ),
        sa.CheckConstraint(
            "actual_material_cost_minor >= 0",
            name="ck_production_orders_actual_material_cost_non_negative",
        ),
    )
    op.create_index("ix_production_orders_production_number", "production_orders", ["production_number"], unique=True)
    op.create_index("ix_production_orders_order_id", "production_orders", ["order_id"], unique=True)
    op.create_index("ix_production_orders_customer_id", "production_orders", ["customer_id"])
    op.create_index("ix_production_orders_custom_request_id", "production_orders", ["custom_request_id"])
    op.create_index("ix_production_orders_status", "production_orders", ["status"])
    op.create_index("ix_production_orders_assigned_worker_id", "production_orders", ["assigned_worker_id"])

    # Production Material Reservations table
    # Use String with CHECK constraint for status (works on both PostgreSQL and SQLite)
    op.create_table(
        "production_material_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "production_order_id",
            sa.Uuid(),
            sa.ForeignKey("production_orders.id", ondelete="CASCADE", name="fk_prod_mat_res_prod_order_id_prod_orders"),
            nullable=False,
        ),
        sa.Column(
            "material_id",
            sa.Uuid(),
            sa.ForeignKey("materials.id", ondelete="RESTRICT", name="fk_prod_mat_res_material_id_materials"),
            nullable=False,
        ),
        # Immutable snapshot fields
        sa.Column("material_name", sa.String(120), nullable=False),
        sa.Column("material_code", sa.String(40), nullable=False),
        sa.Column("material_unit", sa.String(20), nullable=False),
        sa.Column("quantity_required", sa.Numeric(12, 3), nullable=False),
        sa.Column("material_spec", sa.Text(), nullable=True),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        # Mutable tracking fields
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("quantity_reserved", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("quantity_consumed", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("quantity_wasted", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("quantity_returned", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("quantity_released", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "fully_consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity_required >= 0", name="ck_prod_mat_res_qty_required_non_negative"),
        sa.CheckConstraint("quantity_reserved >= 0", name="ck_prod_mat_res_qty_reserved_non_negative"),
        sa.CheckConstraint("quantity_consumed >= 0", name="ck_prod_mat_res_qty_consumed_non_negative"),
        sa.CheckConstraint("quantity_wasted >= 0", name="ck_prod_mat_res_qty_wasted_non_negative"),
        sa.CheckConstraint("quantity_returned >= 0", name="ck_prod_mat_res_qty_returned_non_negative"),
        sa.CheckConstraint("quantity_released >= 0", name="ck_prod_mat_res_qty_released_non_negative"),
        sa.CheckConstraint(
            "quantity_consumed + quantity_wasted + quantity_returned + quantity_released <= quantity_reserved",
            name="ck_prod_mat_res_remaining_reserved_non_negative",
        ),
    )
    op.create_index("ix_prod_mat_res_production_order_id", "production_material_reservations", ["production_order_id"])
    op.create_index("ix_prod_mat_res_material_id", "production_material_reservations", ["material_id"])
    op.create_index("ix_prod_mat_res_status", "production_material_reservations", ["status"])
    op.create_index(
        "ix_prod_mat_res_prod_order_material",
        "production_material_reservations",
        ["production_order_id", "material_id"],
    )

    if is_postgresql:
        # Add CHECK constraints for enum values on PostgreSQL
        op.create_check_constraint(
            "ck_production_orders_status_valid",
            "production_orders",
            text(
                "status IN ('pending', 'planned', 'materials_reserved', 'in_production', "
                "'paused', 'quality_check', 'ready', 'completed', 'cancelled')"
            ),
        )
        op.create_check_constraint(
            "ck_prod_mat_res_status_valid",
            "production_material_reservations",
            text("status IN ('pending','reserved','released','consumed','cancelled')"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == "postgresql"

    # Drop the child table first: production_material_reservations references
    # production_orders via FK. Dropping tables removes their indexes too.
    op.execute("DROP TABLE IF EXISTS production_material_reservations")
    op.execute("DROP TABLE IF EXISTS production_orders")

    if is_postgresql:
        op.execute("DROP TYPE IF EXISTS productionorderstatus")
        op.execute("DROP TYPE IF EXISTS productionmaterialreservationstatus")
