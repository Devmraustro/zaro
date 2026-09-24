"""catalog localization tables: product_localizations, category_localizations

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-17

Display-field translations (name/description) per locale (en/fr/ar) for
products and categories. Canonical text stays on the parent table; these
rows override for a locale and fall back to English otherwise.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_localizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_product_localizations_product_id_products"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "locale", name="uq_product_localizations_product_id_locale"),
        sa.CheckConstraint("locale IN ('en','fr','ar')", name="ck_product_localizations_locale_valid"),
    )
    op.create_index("ix_product_localizations_product_id", "product_localizations", ["product_id"])
    op.create_index("ix_product_localizations_locale", "product_localizations", ["locale"])

    op.create_table(
        "category_localizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="CASCADE", name="fk_category_localizations_category_id_categories"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("category_id", "locale", name="uq_category_localizations_category_id_locale"),
        sa.CheckConstraint("locale IN ('en','fr','ar')", name="ck_category_localizations_locale_valid"),
    )
    op.create_index("ix_category_localizations_category_id", "category_localizations", ["category_id"])
    op.create_index("ix_category_localizations_locale", "category_localizations", ["locale"])


def downgrade() -> None:
    op.drop_table("category_localizations")
    op.drop_table("product_localizations")
