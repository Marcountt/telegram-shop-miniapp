from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Currency = Literal["BYN", "RUB"]
Section = Literal["men", "women", "unisex"]
ProductGroup = Literal["clothing", "shoes"]


class StoreModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StoreCategoryOut(StoreModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    group_key: ProductGroup


class ProductCardOut(StoreModel):
    id: UUID
    category_id: UUID
    category_name: str
    group: ProductGroup
    title: str
    brand: Optional[str]
    section: Section
    images: list[dict[str, object]]
    sizes: list[str]
    is_new: bool
    currency: Currency
    price: Decimal
    original_price: Optional[Decimal]
    on_sale: bool
    stock: int
    sold: bool
    created_at: datetime


class ProductPageOut(StoreModel):
    items: list[ProductCardOut]
    page: int
    page_size: int
    total: int
    total_pages: int
    currency: Currency


class VariantOut(StoreModel):
    id: UUID
    size: str
    color: str
    stock: int
    currency: Currency
    price: Decimal


class ProductDetailOut(ProductCardOut):
    description: Optional[str]
    sizes: list[str]
    colors: list[str]
    variants: list[VariantOut]


class PreferencesOut(StoreModel):
    section: Section
    currency: Currency


class CustomerProfileOut(StoreModel):
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    photo_url: Optional[str]
    preferred_section: Section
    preferred_currency: Currency
    is_admin: bool


class StoreSizeOptionOut(StoreModel):
    id: UUID
    group_key: ProductGroup
    value: str
    sort_order: int


class PreferencesUpdate(BaseModel):
    section: Optional[Section] = None
    currency: Optional[Currency] = None

    @model_validator(mode="after")
    def require_a_change(self) -> "PreferencesUpdate":
        if self.section is None and self.currency is None:
            raise ValueError("Укажите хотя бы одну настройку.")
        return self


class FavoritePageOut(StoreModel):
    items: list[ProductCardOut]
    page: int
    page_size: int
    total: int
    currency: Currency


class CartItemCreate(BaseModel):
    variant_id: UUID
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartLineOut(StoreModel):
    variant_id: UUID
    product_id: UUID
    title: str
    image: Optional[dict[str, object]]
    size: str
    color: str
    quantity: int
    stock: int
    currency: Currency
    unit_price: Decimal
    line_total: Decimal


class CartOut(StoreModel):
    items: list[CartLineOut]
    currency: Currency
    items_total: Decimal
    item_count: int


class OrderCreate(BaseModel):
    recipient_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=5, max_length=32)
    delivery_method_id: UUID
    city: str = Field(min_length=2, max_length=60)
    address: Optional[str] = Field(default=None, min_length=3, max_length=150)
    branch: Optional[str] = Field(default=None, min_length=1, max_length=100)
    comment: Optional[str] = Field(default=None, max_length=200)

    @field_validator("recipient_name", "phone", "city", "address", "branch")
    @classmethod
    def trim_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Поле не может быть пустым.")
        return normalized

    @model_validator(mode="after")
    def require_delivery_location(self) -> "OrderCreate":
        if not self.address and not self.branch:
            raise ValueError("Укажите адрес доставки или номер/адрес отделения.")
        return self


class OrderLineOut(StoreModel):
    product_id: Optional[UUID]
    product_name: str
    size: str
    color: str
    quantity: int
    currency: Currency
    unit_price: Decimal
    line_total: Decimal


class OrderSummaryOut(StoreModel):
    id: UUID
    status: str
    recipient_name: str
    phone: str
    delivery_method_name: str
    city: str
    delivery_address: str
    currency: Currency
    items_total: Decimal
    total: Decimal
    created_at: datetime


class OrderDetailOut(OrderSummaryOut):
    delivery_price: Optional[Decimal]
    delivery_price_note: Optional[str]
    comment: Optional[str]
    items: list[OrderLineOut]


class OrderCreatedOut(BaseModel):
    order: OrderDetailOut
    manager_link: str


class OrderPageOut(BaseModel):
    items: list[OrderSummaryOut]
    page: int
    page_size: int
    total: int


class DeliveryMethodOut(StoreModel):
    id: UUID
    code: str
    name: str
    currency: Currency
    price: Optional[Decimal]
    price_note: Optional[str]


class PublicStoreSettingsOut(BaseModel):
    manager_username: str
    reviews_url: str
    store_name: str
    currency: Currency
    delivery_methods: list[DeliveryMethodOut]
