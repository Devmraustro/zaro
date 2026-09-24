"""order delivery address snapshot

Revision ID: 0015
Revises: 0010
Create Date: 2026-09-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_wilaya", sa.String(10), nullable=True))
    op.add_column("orders", sa.Column("delivery_commune", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("delivery_address", sa.Text(), nullable=True))

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # PostgreSQL forbids subqueries inside CHECK constraints, so the
        # delivery snapshot columns are intentionally unconstrained at the
        # reference level (they are immutable historical snapshots, and the
        # wilayas/communes reference tables are seeded at runtime). Only the
        # address length bound is enforced here. SQLite cannot ALTER TABLE to
        # add a CHECK constraint, so this stays PostgreSQL-only.
        op.create_check_constraint(
            "ck_orders_delivery_address_length",
            "orders",
            sa.text("length(delivery_address) <= 500"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_orders_delivery_address_length", "orders")
    op.drop_column("orders", "delivery_address")
    op.drop_column("orders", "delivery_commune")
    op.drop_column("orders", "delivery_wilaya")
