"""Добавить административные поля цен и справочник размеров.

Идентификатор ревизии: 0006_admin_catalog
Предыдущая ревизия: 0005_notification_outbox
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_admin_catalog"
down_revision: Union[str, None] = "0005_notification_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("price_rub", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("sale_price_rub", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column(
            "is_new",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_products_price_rub_nonnegative"),
        "products",
        "price_rub IS NULL OR price_rub >= 0",
    )
    op.create_check_constraint(
        op.f("ck_products_sale_price_rub_range"),
        "products",
        "sale_price_rub IS NULL OR "
        "(sale_price_rub >= 0 AND price_rub IS NOT NULL AND sale_price_rub < price_rub)",
    )
    op.create_table(
        "size_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_key", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "group_key IN ('clothing', 'shoes')",
            name=op.f("ck_size_options_group_key_valid"),
        ),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_size_options_sort_order_nonnegative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_size_options")),
        sa.UniqueConstraint("group_key", "value", name=op.f("uq_size_options_group_value")),
    )
    op.create_index(
        op.f("ix_size_options_group_active"),
        "size_options",
        ["group_key", "is_active", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_size_options_group_active"), table_name="size_options")
    op.drop_table("size_options")
    op.drop_constraint(op.f("ck_products_sale_price_rub_range"), "products", type_="check")
    op.drop_constraint(op.f("ck_products_price_rub_nonnegative"), "products", type_="check")
    op.drop_column("products", "is_new")
    op.drop_column("products", "sale_price_rub")
    op.drop_column("products", "price_rub")
