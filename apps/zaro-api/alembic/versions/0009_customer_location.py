"""customer location fields: wilaya on customers; wilaya/commune/address on custom_requests

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-17

Adds DZ province (wilaya) awareness to customer records and captures the
submission-time delivery location snapshot on custom requests so staff can
route/plan around regions even when the customer record is later merged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("wilaya", sa.String(60), nullable=True))
    op.create_index("ix_customers_wilaya", "customers", ["wilaya"])

    op.add_column("custom_requests", sa.Column("wilaya", sa.String(60), nullable=True))
    op.add_column("custom_requests", sa.Column("commune", sa.String(100), nullable=True))
    op.add_column("custom_requests", sa.Column("address", sa.Text(), nullable=True))
    op.create_index("ix_custom_requests_wilaya", "custom_requests", ["wilaya"])


def downgrade() -> None:
    op.drop_index("ix_custom_requests_wilaya", table_name="custom_requests")
    op.drop_column("custom_requests", "address")
    op.drop_column("custom_requests", "commune")
    op.drop_column("custom_requests", "wilaya")

    op.drop_index("ix_customers_wilaya", table_name="customers")
    op.drop_column("customers", "wilaya")
