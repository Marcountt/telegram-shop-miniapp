"""Подготовить каталог магазина, склад, корзину и заказы.

Идентификатор ревизии: 0004_store_api
Предыдущая ревизия: 0003_user_photo_url
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_store_api"
down_revision: Union[str, None] = "0003_user_photo_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("group_key", sa.String(length=20), server_default="clothing", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_categories_group_key_valid"),
        "categories",
        "group_key IN ('clothing', 'shoes')",
    )
    op.execute("UPDATE categories SET group_key = 'shoes' WHERE slug = 'obuv'")

    op.add_column("users", sa.Column("preferred_section", sa.String(length=20), server_default="unisex", nullable=False))
    op.add_column("users", sa.Column("preferred_currency", sa.String(length=3), server_default="BYN", nullable=False))
    op.create_check_constraint(
        op.f("ck_users_preferred_section_valid"),
        "users",
        "preferred_section IN ('men', 'women', 'unisex')",
    )
    op.create_check_constraint(
        op.f("ck_users_preferred_currency_valid"),
        "users",
        "preferred_currency IN ('BYN', 'RUB')",
    )

    op.add_column("products", sa.Column("brand", sa.String(length=120), nullable=True))
    op.add_column(
        "products",
        sa.Column("section", sa.String(length=20), server_default="unisex", nullable=False),
    )
    op.add_column("products", sa.Column("sale_price_byn", sa.Numeric(10, 2), nullable=True))
    op.create_check_constraint(
        op.f("ck_products_section_valid"),
        "products",
        "section IN ('men', 'women', 'unisex')",
    )
    op.create_check_constraint(
        op.f("ck_products_sale_price_range"),
        "products",
        "sale_price_byn IS NULL OR (sale_price_byn >= 0 AND sale_price_byn < price_byn)",
    )

    op.create_table(
        "product_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("size", sa.String(length=40), server_default="", nullable=False),
        sa.Column("color", sa.String(length=80), server_default="", nullable=False),
        sa.Column("stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("price_byn", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("stock >= 0", name=op.f("ck_product_variants_stock_nonnegative")),
        sa.CheckConstraint(
            "price_byn IS NULL OR price_byn >= 0",
            name=op.f("ck_product_variants_price_byn_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variants")),
        sa.UniqueConstraint(
            "product_id", "size", "color",
            name="uq_product_variants_product_size_color",
        ),
    )
    op.create_index(
        "ix_product_variants_product_stock",
        "product_variants",
        ["product_id", "stock"],
        unique=False,
    )

    op.create_table(
        "product_favorites",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name=op.f("fk_product_favorites_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_product_favorites_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "product_id", name=op.f("pk_product_favorites")),
    )

    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity BETWEEN 1 AND 99", name=op.f("ck_cart_items_quantity_range")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_cart_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["product_variants.id"],
            name=op.f("fk_cart_items_variant_id_product_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cart_items")),
        sa.UniqueConstraint("user_id", "variant_id", name="uq_cart_items_user_variant"),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("recipient_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("delivery_method_name", sa.String(length=100), nullable=False),
        sa.Column("delivery_method_code", sa.String(length=40), nullable=False),
        sa.Column("delivery_price_byn", sa.Numeric(10, 2), nullable=True),
        sa.Column("delivery_price_note", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("delivery_address", sa.String(length=300), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("items_total_byn", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_byn", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("items_total_byn >= 0", name=op.f("ck_orders_items_total_nonnegative")),
        sa.CheckConstraint(
            "delivery_price_byn IS NULL OR delivery_price_byn >= 0",
            name=op.f("ck_orders_delivery_price_nonnegative"),
        ),
        sa.CheckConstraint("total_byn >= 0", name=op.f("ck_orders_total_nonnegative")),
        sa.CheckConstraint(
            "currency IN ('BYN', 'RUB')", name=op.f("ck_orders_currency_valid")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'shipped', 'completed', 'cancelled')",
            name=op.f("ck_orders_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_orders_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index("ix_orders_user_created_at", "orders", ["user_id", "created_at"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("size", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_byn", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_items_quantity_positive")),
        sa.CheckConstraint(
            "unit_price_byn >= 0", name=op.f("ck_order_items_unit_price_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["product_variants.id"],
            name=op.f("fk_order_items_variant_id_product_variants"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
    )


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_index("ix_orders_user_created_at", table_name="orders")
    op.drop_table("orders")
    op.drop_table("cart_items")
    op.drop_table("product_favorites")
    op.drop_index("ix_product_variants_product_stock", table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_constraint(op.f("ck_products_sale_price_range"), "products", type_="check")
    op.drop_constraint(op.f("ck_products_section_valid"), "products", type_="check")
    op.drop_column("products", "sale_price_byn")
    op.drop_column("products", "section")
    op.drop_column("products", "brand")
    op.drop_constraint(op.f("ck_users_preferred_currency_valid"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_preferred_section_valid"), "users", type_="check")
    op.drop_column("users", "preferred_currency")
    op.drop_column("users", "preferred_section")
    op.drop_constraint(op.f("ck_categories_group_key_valid"), "categories", type_="check")
    op.drop_column("categories", "group_key")
