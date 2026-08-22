"""commerce core: catalog, materials, customers, custom requests, file assets

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Models use JSONType (JSONB on PostgreSQL, JSON elsewhere); migrations must match.
JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("product_code", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="SET NULL", name="fk_products_category_id_categories"),
            nullable=True,
        ),
        sa.Column("dimensions", JSONType, nullable=True),
        sa.Column("materials_spec", JSONType, nullable=True),
        sa.Column("weight_kg", sa.Numeric(8, 2), nullable=True),
        sa.Column("selling_price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("production_time_days", sa.Integer(), nullable=True),
        sa.Column("stock_status", sa.String(20), nullable=False, server_default="made_to_order"),
        sa.Column("delivery_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("delivery_info", sa.Text(), nullable=True),
        sa.Column("meta_title", sa.String(200), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_products_created_by_users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_products_product_code", "products", ["product_code"], unique=True)
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_status", "products", ["status"])

    op.create_table(
        "product_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_product_variants_product_id_products"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(60), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("attributes", JSONType, nullable=True),
        sa.Column("price_override_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_product_variants_sku", "product_variants", ["sku"], unique=True)
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])

    op.create_table(
        "materials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_materials_code", "materials", ["code"], unique=True)

    op.create_table(
        "material_prices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "material_id",
            sa.Uuid(),
            sa.ForeignKey("materials.id", ondelete="CASCADE", name="fk_material_prices_material_id_materials"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_material_prices_created_by_users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("material_id", "effective_from", name="uq_material_prices_material_effective"),
    )
    op.create_index("ix_material_prices_material_id", "material_prices", ["material_id"])

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=True, unique=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("municipality", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_customers_user_id_users"),
            nullable=True,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # email's unique=True already provides an index; avoid a duplicate.
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "custom_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reference", sa.String(20), nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_custom_requests_customer_id_customers"),
            nullable=True,
        ),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("product_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("desired_dimensions", sa.Text(), nullable=True),
        sa.Column("materials", sa.Text(), nullable=True),
        sa.Column("colors", sa.Text(), nullable=True),
        sa.Column("finish", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("budget_min_minor", sa.BigInteger(), nullable=True),
        sa.Column("budget_max_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("source", sa.String(20), nullable=False, server_default="website"),
        sa.Column(
            "assigned_to",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_custom_requests_assigned_to_users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_custom_requests_reference", "custom_requests", ["reference"], unique=True)
    op.create_index("ix_custom_requests_customer_id", "custom_requests", ["customer_id"])
    op.create_index("ix_custom_requests_status", "custom_requests", ["status"])

    op.create_table(
        "file_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_file_assets_owner_user_id_users"),
            nullable=True,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_file_assets_customer_id_customers"),
            nullable=True,
        ),
        sa.Column(
            "custom_request_id",
            sa.Uuid(),
            sa.ForeignKey(
                "custom_requests.id", ondelete="CASCADE", name="fk_file_assets_custom_request_id_custom_requests"
            ),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_file_assets_product_id_products"),
            nullable=True,
        ),
        sa.Column("media_kind", sa.String(20), nullable=True),
        sa.Column("alt_text", sa.String(300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "uploaded_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_file_assets_uploaded_by_user_id_users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # storage_key uniqueness comes from uq_file_assets_storage_key (inline unique=True);
    # the model declares no separate index for it.
    op.create_index("ix_file_assets_purpose", "file_assets", ["purpose"])
    op.create_index("ix_file_assets_customer_id", "file_assets", ["customer_id"])
    op.create_index("ix_file_assets_custom_request_id", "file_assets", ["custom_request_id"])
    op.create_index("ix_file_assets_product_id", "file_assets", ["product_id"])


def downgrade() -> None:
    op.drop_table("file_assets")
    op.drop_table("custom_requests")
    op.drop_table("customers")
    op.drop_table("material_prices")
    op.drop_table("materials")
    op.drop_table("product_variants")
    op.drop_table("products")
    op.drop_table("categories")
