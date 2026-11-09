"""Создать начальную схему Local Catalog.

Идентификатор ревизии: 0001_initial_schema
Предыдущая ревизия:
Дата создания: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


place_status = sa.Enum(
    "draft",
    "pending",
    "published",
    "rejected",
    "archived",
    name="place_status",
    native_enum=False,
    create_constraint=True,
)
submission_status = sa.Enum(
    "pending",
    "approved",
    "rejected",
    name="submission_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_users_telegram_id")),
    )

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"], name=op.f("fk_categories_parent_id_categories"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name=op.f("uq_categories_slug")),
    )

    op.create_table(
        "places",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("telegram", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("working_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "photos",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", place_status, server_default="draft", nullable=False),
        sa.Column("rating_cache", sa.Numeric(precision=3, scale=2), server_default="0", nullable=False),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name=op.f("ck_places_latitude_range")),
        sa.CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name=op.f("ck_places_longitude_range")),
        sa.CheckConstraint("rating_cache BETWEEN 0 AND 5", name=op.f("ck_places_rating_cache_range")),
        sa.CheckConstraint("review_count >= 0", name=op.f("ck_places_review_count_nonnegative")),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name=op.f("fk_places_category_id_categories"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_places_owner_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_places")),
    )
    op.create_index("ix_places_status_category", "places", ["status", "category_id"], unique=False)
    op.create_index("ix_places_status_district", "places", ["status", "district"], unique=False)

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_reviews_rating_range")),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], name=op.f("fk_reviews_place_id_places"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_reviews_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.UniqueConstraint("user_id", "place_id", name="uq_reviews_user_place"),
    )
    op.create_index(op.f("ix_reviews_place_id"), "reviews", ["place_id"], unique=False)

    op.create_table(
        "favorites",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], name=op.f("fk_favorites_place_id_places"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_favorites_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "place_id", name=op.f("pk_favorites")),
    )

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", submission_status, server_default="pending", nullable=False),
        sa.Column("moderator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"], name=op.f("fk_submissions_moderator_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], name=op.f("fk_submissions_place_id_places"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitter_id"], ["users.id"], name=op.f("fk_submissions_submitter_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index("ix_submissions_status_created_at", "submissions", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_submissions_status_created_at", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("favorites")
    op.drop_index(op.f("ix_reviews_place_id"), table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_places_status_district", table_name="places")
    op.drop_index("ix_places_status_category", table_name="places")
    op.drop_table("places")
    op.drop_table("categories")
    op.drop_table("users")
