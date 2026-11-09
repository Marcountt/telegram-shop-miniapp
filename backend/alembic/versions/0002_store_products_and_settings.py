"""Добавить товары и настройки магазина DEMO STORE.

Идентификатор ревизии: 0002_store_products_and_settings
Предыдущая ревизия: 0001_initial_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_store_products_and_settings"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("manager_username", sa.String(length=64), nullable=False),
        sa.Column("reviews_url", sa.String(length=2048), nullable=False),
        sa.Column("byn_to_rub_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("welcome_text", sa.Text(), nullable=False),
        sa.Column("delivery_info_text", sa.Text(), nullable=False),
        sa.Column("how_to_order_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("store_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_store_settings_singleton")),
        sa.CheckConstraint(
            "byn_to_rub_rate > 0", name=op.f("ck_store_settings_byn_to_rub_rate_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_settings")),
    )

    op.create_table(
        "delivery_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price_byn", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_note", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "price_byn IS NULL OR price_byn >= 0",
            name=op.f("ck_delivery_methods_price_byn_nonnegative"),
        ),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_delivery_methods_sort_order_nonnegative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_methods")),
        sa.UniqueConstraint("code", name=op.f("uq_delivery_methods_code")),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_byn", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "photos",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "sizes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "colors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price_byn >= 0", name=op.f("ck_products_price_byn_nonnegative")),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_products_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("slug", name=op.f("uq_products_slug")),
    )
    op.create_index(
        "ix_products_category_active", "products", ["category_id", "is_active"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_products_category_active", table_name="products")
    op.drop_table("products")
    op.drop_table("delivery_methods")
    op.drop_table("store_settings")
