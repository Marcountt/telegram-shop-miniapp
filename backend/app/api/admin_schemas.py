"""Pydantic-схемы административного API."""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from app.api.store_schemas import OrderDetailOut, OrderSummaryOut, ProductGroup, Section


class AdminModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AdminSizeInput(BaseModel):
    size: str = Field(min_length=1, max_length=40)
    quantity: int = Field(default=1, ge=0, le=100000)
    color: str = Field(default="", max_length=80)

    @field_validator("size")
    @classmethod
    def trim_size_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Размер не может быть пустым.")
        return normalized

    @field_validator("color")
    @classmethod
    def trim_color_text(cls, value: str) -> str:
        return value.strip()


class AdminProductWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    section: Section = "unisex"
    category_id: UUID
    price_byn: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    price_rub: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    rub_price_mode: Literal["auto", "manual"] = "auto"
    old_price_byn: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    old_price_rub: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    sizes: list[AdminSizeInput] = Field(default_factory=list, max_length=100)
    is_new: bool = False

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название товара обязательно.")
        return normalized

    @field_validator("brand", "description")
    @classmethod
    def trim_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_prices_and_sizes(self) -> "AdminProductWrite":
        if self.rub_price_mode == "manual" and self.price_rub is None:
            raise ValueError("Для ручного курса укажите цену в RUB.")
        if self.rub_price_mode == "auto" and (
            self.price_rub is not None or self.old_price_rub is not None
        ):
            raise ValueError("При автоматическом курсе цена в RUB рассчитывается из курса магазина.")
        if self.old_price_rub is not None and self.old_price_byn is None:
            raise ValueError("Старая цена в RUB указывается вместе со старой ценой в BYN.")
        if self.old_price_byn is not None and self.old_price_byn <= self.price_byn:
            raise ValueError("Старая цена в BYN должна быть выше текущей.")
        if (
            self.old_price_rub is not None
            and self.price_rub is not None
            and self.old_price_rub <= self.price_rub
        ):
            raise ValueError("Старая цена в RUB должна быть выше текущей.")
        variants = [(item.size.casefold(), item.color.casefold()) for item in self.sizes]
        if len(variants) != len(set(variants)):
            raise ValueError("Размеры и цвета товара не должны повторяться.")
        return self


class AdminVariantOut(AdminModel):
    id: UUID
    size: str
    color: str
    stock: int


class AdminProductOut(AdminModel):
    id: UUID
    title: str
    brand: Optional[str]
    description: Optional[str]
    section: Section
    category_id: UUID
    category_name: str
    price_byn: Decimal
    price_rub: Optional[Decimal]
    old_price_byn: Optional[Decimal]
    old_price_rub: Optional[Decimal]
    is_new: bool
    is_active: bool
    sold_at: Optional[datetime]
    images: list[dict[str, object]]
    variants: list[AdminVariantOut]
    created_at: datetime
    updated_at: datetime


class AdminProductPage(BaseModel):
    items: list[AdminProductOut]
    page: int
    page_size: int
    total: int


class AdminDashboardProduct(BaseModel):
    id: UUID
    title: str
    category_name: str
    stock: int
    image_url: Optional[str]


class AdminDashboardOut(BaseModel):
    pending_orders: int
    today_orders: int
    today_revenue_byn: Decimal
    week_orders: int
    week_revenue_byn: Decimal
    one_size_left: list[AdminDashboardProduct]


class AdminCategoryWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: Optional[str] = None
    group_key: ProductGroup
    is_active: bool = True

    @field_validator("name", "slug")
    @classmethod
    def trim_category_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название и slug категории обязательны.")
        return normalized


class AdminCategoryOut(AdminModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    group_key: ProductGroup
    is_active: bool


class AdminSizeOptionWrite(BaseModel):
    group_key: ProductGroup
    value: str = Field(min_length=1, max_length=40)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)

    @field_validator("value")
    @classmethod
    def trim_size_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Размер не может быть пустым.")
        return normalized


class AdminSizeOptionOut(AdminModel):
    id: UUID
    group_key: ProductGroup
    value: str
    is_active: bool
    sort_order: int


class AdminOrderOut(BaseModel):
    order: OrderSummaryOut
    customer_telegram_id: int
    customer_username: Optional[str]


class AdminOrderDetailOut(BaseModel):
    order: OrderDetailOut
    customer_telegram_id: int
    customer_username: Optional[str]


class AdminOrderPage(BaseModel):
    items: list[AdminOrderOut]
    page: int
    page_size: int
    total: int


class AdminOrderStatusUpdate(BaseModel):
    action: Literal["confirm", "shipped", "delivered", "cancel"]


class AdminDeliveryWrite(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    price_byn: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    price_note: Optional[str] = Field(default=None, max_length=120)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_price_or_note(self) -> "AdminDeliveryWrite":
        if self.price_byn is None and not self.price_note:
            raise ValueError("Укажите цену доставки или пояснение о стоимости.")
        return self

    @field_validator("name", "code")
    @classmethod
    def trim_delivery_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название и код доставки обязательны.")
        return normalized


class AdminDeliveryOut(AdminModel):
    id: UUID
    code: str
    name: str
    price_byn: Optional[Decimal]
    price_note: Optional[str]
    is_active: bool
    sort_order: int


class AdminSettingsPatch(BaseModel):
    manager_username: Optional[str] = Field(default=None, min_length=1, max_length=64)
    reviews_url: Optional[HttpUrl] = None
    store_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    welcome_text: Optional[str] = Field(default=None, min_length=1)
    delivery_info_text: Optional[str] = Field(default=None, min_length=1)
    how_to_order_steps: Optional[list[str]] = Field(
        default=None, min_length=4, max_length=4
    )
    byn_to_rub_rate: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )

    @field_validator(
        "manager_username", "store_name", "welcome_text", "delivery_info_text"
    )
    @classmethod
    def trim_settings_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("how_to_order_steps")
    @classmethod
    def validate_order_steps(
        cls, value: Optional[list[str]]
    ) -> Optional[list[str]]:
        if value is None:
            return None
        normalized = [step.strip() for step in value]
        if any(not step for step in normalized):
            raise ValueError("Все четыре шага оформления должны быть заполнены.")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "AdminSettingsPatch":
        if not self.model_fields_set:
            raise ValueError("Укажите хотя бы одну настройку для изменения.")
        return self


class AdminSettingsOut(BaseModel):
    manager_username: str
    reviews_url: str
    store_name: str
    welcome_text: str
    delivery_info_text: str
    how_to_order_steps: list[str]
    byn_to_rub_rate: Decimal
    deliveries: list[AdminDeliveryOut]


class AdminImageOut(BaseModel):
    id: UUID
    url: str
    thumbnail_url: str
    alt: str
    is_cover: bool


class AdminImageOrder(BaseModel):
    image_ids: list[UUID] = Field(min_length=1, max_length=20)
