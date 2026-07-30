"""Baseline schema matching current SQLAlchemy models.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendor",
        sa.Column("vendor_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("pricing_mode", sa.String(), nullable=False),
        sa.Column("default_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("vendor_id"),
    )
    op.create_table(
        "product",
        sa.Column("product_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("variant", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("current_stock", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("conversion_ratio", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_table(
        "customer",
        sa.Column("customer_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("type_tag", sa.String(), nullable=True),
        sa.Column("credit_days", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("customer_id"),
    )
    op.create_table(
        "user",
        sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "raw_material_txn",
        sa.Column("txn_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("session", sa.String(), nullable=False),
        sa.Column("quantity_l", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("fat_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("rate_applied", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendor.vendor_id"]),
        sa.PrimaryKeyConstraint("txn_id"),
    )
    op.create_table(
        "payment",
        sa.Column("payment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("party_type", sa.String(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("linked_txn_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("payment_id"),
    )
    op.create_table(
        "production_batch",
        sa.Column("batch_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("raw_milk_consumed_l", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("output_qty", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["product.product_id"]),
        sa.PrimaryKeyConstraint("batch_id"),
    )
    op.create_table(
        "order_txn",
        sa.Column("order_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("planning_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.customer_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["product.product_id"]),
        sa.PrimaryKeyConstraint("order_id"),
    )


def downgrade() -> None:
    op.drop_table("order_txn")
    op.drop_table("production_batch")
    op.drop_table("payment")
    op.drop_table("raw_material_txn")
    op.drop_table("user")
    op.drop_table("customer")
    op.drop_table("product")
    op.drop_table("vendor")
