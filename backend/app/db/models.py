from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB as PostgreSQLJSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSONB = JSON().with_variant(PostgreSQLJSONB(), "postgresql")
UUID = Uuid


class PlaceStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def enum_type(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "preferred_section IN ('men', 'women', 'unisex')",
            name="preferred_section_valid",
        ),
        CheckConstraint(
            "preferred_currency IN ('BYN', 'RUB')",
            name="preferred_currency_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    preferred_section: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unisex", server_default="unisex"
    )
    preferred_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="BYN", server_default="BYN"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    places: Mapped[list["Place"]] = relationship(back_populates="owner")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user")
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="submitter", foreign_keys="Submission.submitter_id"
    )


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("group_key IN ('clothing', 'shoes')", name="group_key_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    group_key: Mapped[str] = mapped_column(
        String(20), nullable=False, default="clothing", server_default="clothing"
    )

    parent: Mapped[Optional["Category"]] = relationship(
        back_populates="children", remote_side="Category.id"
    )
    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    places: Mapped[list["Place"]] = relationship(back_populates="category")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Place(TimestampMixin, Base):
    __tablename__ = "places"
    __table_args__ = (
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("rating_cache BETWEEN 0 AND 5", name="rating_cache_range"),
        CheckConstraint("review_count >= 0", name="review_count_nonnegative"),
        Index("ix_places_status_category", "status", "category_id"),
        Index("ix_places_status_district", "status", "district"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    telegram: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    working_hours: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    photos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    status: Mapped[PlaceStatus] = mapped_column(
        enum_type(PlaceStatus, "place_status"),
        nullable=False,
        default=PlaceStatus.DRAFT,
        server_default=PlaceStatus.DRAFT.value,
    )
    rating_cache: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    owner: Mapped[Optional[User]] = relationship(back_populates="places")
    category: Mapped[Optional[Category]] = relationship(back_populates="places")
    reviews: Mapped[list["Review"]] = relationship(back_populates="place", cascade="all, delete-orphan")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="place", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="place")


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        UniqueConstraint("user_id", "place_id", name="uq_reviews_user_place"),
        Index("ix_reviews_place_id", "place_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="reviews")
    place: Mapped[Place] = relationship(back_populates="reviews")


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="favorites")
    place: Mapped[Place] = relationship(back_populates="favorites")


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submitter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        enum_type(SubmissionStatus, "submission_status"),
        nullable=False,
        default=SubmissionStatus.PENDING,
        server_default=SubmissionStatus.PENDING.value,
    )
    moderator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitter: Mapped[User] = relationship(back_populates="submissions", foreign_keys=[submitter_id])
    moderator: Mapped[Optional[User]] = relationship(foreign_keys=[moderator_id])
    place: Mapped[Optional[Place]] = relationship(back_populates="submissions")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_byn >= 0", name="price_byn_nonnegative"),
        CheckConstraint(
            "sale_price_byn IS NULL OR (sale_price_byn >= 0 AND sale_price_byn < price_byn)",
            name="sale_price_range",
        ),
        CheckConstraint(
            "price_rub IS NULL OR price_rub >= 0",
            name="price_rub_nonnegative",
        ),
        CheckConstraint(
            "sale_price_rub IS NULL OR "
            "(sale_price_rub >= 0 AND price_rub IS NOT NULL AND sale_price_rub < price_rub)",
            name="sale_price_rub_range",
        ),
        CheckConstraint("section IN ('men', 'women', 'unisex')", name="section_valid"),
        Index("ix_products_category_active", "category_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_byn: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    photos: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    sizes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    colors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    section: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unisex", server_default="unisex"
    )
    sale_price_byn: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_rub: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sale_price_rub: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    category: Mapped[Category] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(TimestampMixin, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="stock_nonnegative"),
        CheckConstraint("price_byn IS NULL OR price_byn >= 0", name="price_byn_nonnegative"),
        UniqueConstraint(
            "product_id",
            "size",
            "color",
            name="uq_product_variants_product_size_color",
        ),
        Index("ix_product_variants_product_stock", "product_id", "stock"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    size: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    color: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    price_byn: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    product: Mapped[Product] = relationship(back_populates="variants")


class SizeOption(TimestampMixin, Base):
    __tablename__ = "size_options"
    __table_args__ = (
        CheckConstraint("group_key IN ('clothing', 'shoes')", name="group_key_valid"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        UniqueConstraint("group_key", "value", name="uq_size_options_group_value"),
        Index("ix_size_options_group_active", "group_key", "is_active", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    group_key: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class ProductFavorite(Base):
    __tablename__ = "product_favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CartItem(TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 99", name="quantity_range"),
        UniqueConstraint("user_id", "variant_id", name="uq_cart_items_user_variant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("items_total_byn >= 0", name="items_total_nonnegative"),
        CheckConstraint(
            "delivery_price_byn IS NULL OR delivery_price_byn >= 0",
            name="delivery_price_nonnegative",
        ),
        CheckConstraint("total_byn >= 0", name="total_nonnegative"),
        CheckConstraint(
            "currency IN ('BYN', 'RUB')", name="currency_valid"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'shipped', 'completed', 'cancelled')",
            name="status_valid",
        ),
        Index("ix_orders_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_method_name: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_method_code: Mapped[str] = mapped_column(String(40), nullable=False)
    delivery_price_byn: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    delivery_price_note: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(300), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    items_total_byn: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_byn: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_byn >= 0", name="unit_price_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    size: Mapped[str] = mapped_column(String(40), nullable=False)
    color: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_byn: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        Index("ix_notification_outbox_pending", "completed_at", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StoreSettings(TimestampMixin, Base):
    __tablename__ = "store_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("byn_to_rub_rate > 0", name="byn_to_rub_rate_positive"),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, default=1, autoincrement=False
    )
    manager_username: Mapped[str] = mapped_column(String(64), nullable=False)
    reviews_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    byn_to_rub_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    welcome_text: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_info_text: Mapped[str] = mapped_column(Text, nullable=False)
    how_to_order_steps: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    store_name: Mapped[str] = mapped_column(String(120), nullable=False)


class DeliveryMethod(TimestampMixin, Base):
    __tablename__ = "delivery_methods"
    __table_args__ = (
        CheckConstraint("price_byn IS NULL OR price_byn >= 0", name="price_byn_nonnegative"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_byn: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_note: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
