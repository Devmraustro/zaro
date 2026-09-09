"""phase 3 commerce: quotes, orders, manual CCP payments

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-22

Financial invariants enforced at the database level:

- CHECK constraints keep every monetary column non-negative and keep
  total/balance/deposit relationships internally consistent;
- ``orders.quote_id`` is UNIQUE (one order per accepted quote);
- partial UNIQUE indexes guarantee at most one active and at most one
  confirmed deposit payment per order (PostgreSQL; SQLite skips them).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0005"
down_revision: str = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quote_number", sa.String(20), nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_quotes_customer_id_customers"),
            nullable=True,
        ),
        sa.Column(
            "custom_request_id",
            sa.Uuid(),
            sa.ForeignKey("custom_requests.id", ondelete="SET NULL", name="fk_quotes_custom_request_id_custom_requests"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("delivery_fee_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("deposit_percentage", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("deposit_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("balance_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_quotes_created_by_users"),
            nullable=True,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("subtotal_minor >= 0", name="ck_quotes_subtotal_non_negative"),
        sa.CheckConstraint("discount_minor >= 0", name="ck_quotes_discount_non_negative"),
        sa.CheckConstraint("delivery_fee_minor >= 0", name="ck_quotes_delivery_fee_non_negative"),
        sa.CheckConstraint(
            "total_minor = subtotal_minor - discount_minor + delivery_fee_minor",
            name="ck_quotes_total_consistent",
        ),
        sa.CheckConstraint(
            "deposit_amount_minor >= 0 AND deposit_amount_minor <= total_minor",
            name="ck_quotes_deposit_bounds",
        ),
        sa.CheckConstraint("balance_amount_minor >= 0", name="ck_quotes_balance_non_negative"),
        sa.CheckConstraint(
            "deposit_percentage >= 0 AND deposit_percentage <= 100",
            name="ck_quotes_deposit_percentage_bounds",
        ),
    )
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"], unique=True)
    op.create_index("ix_quotes_customer_id", "quotes", ["customer_id"])
    op.create_index("ix_quotes_custom_request_id", "quotes", ["custom_request_id"])
    op.create_index("ix_quotes_status", "quotes", ["status"])

    op.create_table(
        "quote_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "quote_id",
            sa.Uuid(),
            sa.ForeignKey("quotes.id", ondelete="CASCADE", name="fk_quote_lines_quote_id_quotes"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_label", sa.String(30), nullable=True),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_quote_lines_quantity_non_negative"),
        sa.CheckConstraint("unit_price_minor >= 0", name="ck_quote_lines_unit_price_non_negative"),
        sa.CheckConstraint("line_total_minor >= 0", name="ck_quote_lines_total_non_negative"),
    )
    op.create_index("ix_quote_lines_quote_id", "quote_lines", ["quote_id"])
    op.create_index("ix_quote_lines_quote_position", "quote_lines", ["quote_id", "position"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_number", sa.String(20), nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_orders_customer_id_customers"),
            nullable=True,
        ),
        sa.Column(
            "quote_id",
            sa.Uuid(),
            sa.ForeignKey("quotes.id", ondelete="SET NULL", name="fk_orders_quote_id_quotes"),
            nullable=True,
        ),
        sa.Column(
            "custom_request_id",
            sa.Uuid(),
            sa.ForeignKey("custom_requests.id", ondelete="SET NULL", name="fk_orders_custom_request_id_custom_requests"),
            nullable=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_deposit"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("delivery_fee_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("deposit_required_minor", sa.BigInteger(), nullable=False),
        sa.Column("deposit_paid_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("balance_due_minor", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("subtotal_minor >= 0", name="ck_orders_subtotal_non_negative"),
        sa.CheckConstraint("discount_minor >= 0", name="ck_orders_discount_non_negative"),
        sa.CheckConstraint("delivery_fee_minor >= 0", name="ck_orders_delivery_fee_non_negative"),
        sa.CheckConstraint(
            "total_minor = subtotal_minor - discount_minor + delivery_fee_minor",
            name="ck_orders_total_consistent",
        ),
        sa.CheckConstraint(
            "deposit_paid_minor >= 0 AND deposit_paid_minor <= total_minor",
            name="ck_orders_deposit_paid_bounds",
        ),
        sa.CheckConstraint(
            "balance_due_minor = total_minor - deposit_paid_minor",
            name="ck_orders_balance_consistent",
        ),
        sa.CheckConstraint(
            "deposit_required_minor >= 0 AND deposit_required_minor <= total_minor",
            name="ck_orders_deposit_required_bounds",
        ),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_quote_id", "orders", ["quote_id"], unique=True)
    op.create_index("ix_orders_custom_request_id", "orders", ["custom_request_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE", name="fk_order_lines_order_id_orders"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_label", sa.String(30), nullable=True),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_order_lines_quantity_non_negative"),
        sa.CheckConstraint("unit_price_minor >= 0", name="ck_order_lines_unit_price_non_negative"),
        sa.CheckConstraint("line_total_minor >= 0", name="ck_order_lines_total_non_negative"),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])
    op.create_index("ix_order_lines_order_position", "order_lines", ["order_id", "position"])

    op.create_table(
        "payment_configuration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_holder", sa.String(200), nullable=False),
        sa.Column("account_identifier", sa.String(120), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("default_deposit_percentage", sa.Integer(), nullable=False, server_default="40"),
        sa.Column(
            "updated_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_payment_configuration_updated_by_users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("payment_reference", sa.String(30), nullable=False),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE", name="fk_payments_order_id_orders"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_payments_customer_id_customers"),
            nullable=True,
        ),
        sa.Column("method", sa.String(10), nullable=False, server_default="ccp"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="DZD"),
        sa.Column("ccp_account_holder_snapshot", sa.String(200), nullable=False),
        sa.Column("ccp_account_identifier_snapshot", sa.String(120), nullable=False),
        sa.Column("rejection_reason_code", sa.String(40), nullable=True),
        sa.Column("rejection_reason_note", sa.String(500), nullable=True),
        sa.Column(
            "proof_asset_id",
            sa.Uuid(),
            sa.ForeignKey("file_assets.id", ondelete="SET NULL", name="fk_payments_proof_asset_id_file_assets"),
            nullable=True,
        ),
        sa.Column("proof_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_payments_reviewed_by_users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
    )
    op.create_index("ix_payments_payment_reference", "payments", ["payment_reference"], unique=True)
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_customer_id", "payments", ["customer_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    # At most ONE unresolved claim per order (pending/proof_uploaded/under_review).
    # The sqlite_where twin keeps SQLite semantics identical to PostgreSQL
    # (without it SQLite would enforce a full unique index on order_id).
    op.create_index(
        "uq_payments_order_active",
        "payments",
        ["order_id"],
        unique=True,
        postgresql_where=text("status IN ('pending','proof_uploaded','under_review')"),
        sqlite_where=text("status IN ('pending','proof_uploaded','under_review')"),
    )
    # At most ONE confirmed deposit per order.
    op.create_index(
        "uq_payments_order_confirmed",
        "payments",
        ["order_id"],
        unique=True,
        postgresql_where=text("status = 'confirmed'"),
        sqlite_where=text("status = 'confirmed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_order_confirmed", table_name="payments")
    op.drop_index("uq_payments_order_active", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_customer_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_index("ix_payments_payment_reference", table_name="payments")
    op.drop_table("payments")
    op.drop_table("payment_configuration")
    op.drop_index("ix_order_lines_order_position", table_name="order_lines")
    op.drop_index("ix_order_lines_order_id", table_name="order_lines")
    op.drop_table("order_lines")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_custom_request_id", table_name="orders")
    op.drop_index("ix_orders_quote_id", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_index("ix_orders_order_number", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_quote_lines_quote_position", table_name="quote_lines")
    op.drop_index("ix_quote_lines_quote_id", table_name="quote_lines")
    op.drop_table("quote_lines")
    op.drop_index("ix_quotes_status", table_name="quotes")
    op.drop_index("ix_quotes_custom_request_id", table_name="quotes")
    op.drop_index("ix_quotes_customer_id", table_name="quotes")
    op.drop_index("ix_quotes_quote_number", table_name="quotes")
    op.drop_table("quotes")
