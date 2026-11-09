"""Идемпотентное заполнение настроек и демо-каталога BRAND GRODNO."""
import asyncio
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Category,
    DeliveryMethod,
    Product,
    ProductVariant,
    SizeOption,
    StoreSettings,
)
from app.db.session import SessionFactory, engine


HOW_TO_ORDER_STEPS = [
    "Откройте каталог и выберите товары и размеры.",
    "Добавьте выбранные товары в корзину.",
    "Выберите способ доставки и оформите заказ.",
    "Перейдите к менеджеру для подтверждения деталей и оплаты.",
]

STORE_SETTINGS: dict[str, Any] = {
    "manager_username": "your_manager",
    "reviews_url": "https://t.me/your_reviews_channel",
    "byn_to_rub_rate": Decimal("30"),
    "welcome_text": (
        "Просматривайте товары в наличии, выбирайте размер и оформляйте заказ "
        "прямо в каталоге BRAND GRODNO."
    ),
    "delivery_info_text": (
        "Доставляем Белпочтой, Европочтой, СДЭК и курьером. Стоимость и "
        "условия зависят от выбранного способа доставки."
    ),
    "how_to_order_steps": HOW_TO_ORDER_STEPS,
    "store_name": "BRAND GRODNO",
}

DELIVERY_METHODS = [
    {
        "code": "belpochta",
        "name": "Белпочта",
        "price_byn": Decimal("5"),
        "price_note": None,
        "is_active": True,
        "sort_order": 1,
    },
    {
        "code": "europochta",
        "name": "Европочта",
        "price_byn": Decimal("6"),
        "price_note": None,
        "is_active": True,
        "sort_order": 2,
    },
    {
        "code": "cdek",
        "name": "СДЭК",
        "price_byn": None,
        "price_note": "по договорённости",
        "is_active": True,
        "sort_order": 3,
    },
    {
        "code": "courier",
        "name": "Курьер",
        "price_byn": None,
        "price_note": "по договорённости",
        "is_active": True,
        "sort_order": 4,
    },
]

SIZE_OPTIONS = [
    {"group_key": "clothing", "value": value, "sort_order": index}
    for index, value in enumerate(
        ["XS", "S", "M", "L", "XL", "XXL", "Универсальный"], start=1
    )
] + [
    {"group_key": "shoes", "value": str(value), "sort_order": value}
    for value in range(36, 46)
]

CATEGORIES = [
    {"name": "Одежда", "slug": "odezhda", "description": "Одежда BRAND GRODNO.", "group_key": "clothing"},
    {"name": "Аксессуары", "slug": "aksessuary", "description": "Аксессуары BRAND GRODNO.", "group_key": "clothing"},
    {"name": "Обувь", "slug": "obuv", "description": "Обувь BRAND GRODNO.", "group_key": "shoes"},
]

DEMO_PRODUCTS = [
    {
        "slug": "futbolka-brand-grodno",
        "category_slug": "odezhda",
        "name": "Футболка BRAND GRODNO",
        "description": "Базовая футболка из хлопка.",
        "price_byn": Decimal("45"),
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Чёрный", "Белый"],
        "image_text": "T-SHIRT",
    },
    {
        "slug": "hudi-grodno",
        "category_slug": "odezhda",
        "name": "Худи «Гродно»",
        "description": "Тёплое худи свободного кроя.",
        "price_byn": Decimal("120"),
        "sale_price_byn": Decimal("100"),
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Чёрный", "Серый"],
        "image_text": "HOODIE",
    },
    {
        "slug": "svitshot-stary-gorod",
        "category_slug": "odezhda",
        "name": "Свитшот «Старый город»",
        "description": "Свитшот с лаконичным принтом.",
        "price_byn": Decimal("95"),
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Молочный", "Графит"],
        "image_text": "SWEATSHIRT",
    },
    {
        "slug": "longsliv-brand-grodno",
        "category_slug": "odezhda",
        "name": "Лонгслив BRAND GRODNO",
        "description": "Хлопковый лонгслив на каждый день.",
        "price_byn": Decimal("65"),
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Белый", "Чёрный"],
        "image_text": "LONGSLEEVE",
    },
    {
        "slug": "shoper-brand-grodno",
        "category_slug": "aksessuary",
        "name": "Шопер BRAND GRODNO",
        "description": "Тканевая сумка для повседневных вещей.",
        "price_byn": Decimal("20"),
        "sizes": [],
        "colors": ["Натуральный"],
        "image_text": "SHOPPER",
    },
    {
        "slug": "kepka-grodno",
        "category_slug": "aksessuary",
        "name": "Кепка «Гродно»",
        "description": "Кепка с регулируемым размером.",
        "price_byn": Decimal("35"),
        "sizes": ["Универсальный"],
        "colors": ["Чёрный", "Бежевый"],
        "image_text": "CAP",
    },
    {
        "slug": "kedy-brand-grodno",
        "category_slug": "obuv",
        "name": "Кеды BRAND GRODNO",
        "description": "Лёгкие городские кеды.",
        "price_byn": Decimal("140"),
        "sizes": ["36", "37", "38", "39", "40", "41", "42", "43"],
        "colors": ["Белый", "Чёрный"],
        "image_text": "SNEAKERS",
    },
    {
        "slug": "krossovki-grodno",
        "category_slug": "obuv",
        "name": "Кроссовки «Гродно»",
        "description": "Удобные кроссовки для города.",
        "price_byn": Decimal("180"),
        "sizes": ["36", "37", "38", "39", "40", "41", "42", "43"],
        "colors": ["Белый", "Серый"],
        "image_text": "RUNNERS",
    },
]


def placeholder_image_url(image_text: str) -> str:
    return (
        "https://placehold.co/800x1000/F2F0EA/161616.png"
        f"?text=BRAND+GRODNO+{image_text}"
    )


def _insert_for(session: AsyncSession, model: type):
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(model)
    return postgresql_insert(model)


async def seed_database(session: AsyncSession) -> None:
    """Добавляет демо-данные, не перезаписывая настроенные администратором значения."""
    await session.execute(
        _insert_for(session, SizeOption)
        .values(
            [{**option, "id": uuid4(), "is_active": True} for option in SIZE_OPTIONS]
        )
        .on_conflict_do_nothing(
            index_elements=[SizeOption.group_key, SizeOption.value]
        )
    )
    await session.execute(
        _insert_for(session, Category)
        .values(
            [
                {**category, "id": uuid4(), "is_active": True}
                for category in CATEGORIES
            ]
        )
        .on_conflict_do_nothing(index_elements=[Category.slug])
    )
    categories = dict(
        (
            await session.execute(
                select(Category.slug, Category.id).where(
                    Category.slug.in_([category["slug"] for category in CATEGORIES])
                )
            )
        ).all()
    )

    products = [
        {
            "id": uuid4(),
            "category_id": categories[product["category_slug"]],
            "name": product["name"],
            "slug": product["slug"],
            "description": product["description"],
            "price_byn": product["price_byn"],
            "brand": "BRAND GRODNO",
            "section": "unisex",
            "sale_price_byn": product.get("sale_price_byn"),
            "photos": [
                {
                    "url": placeholder_image_url(product["image_text"]),
                    "alt": product["name"],
                }
            ],
            "sizes": product["sizes"],
            "colors": product["colors"],
            "is_active": True,
        }
        for product in DEMO_PRODUCTS
    ]
    product_insert = _insert_for(session, Product).values(products)
    await session.execute(
        product_insert.on_conflict_do_update(
            index_elements=[Product.slug],
            set_={"brand": func.coalesce(Product.brand, product_insert.excluded.brand)},
            where=Product.brand.is_(None),
        )
    )
    product_ids = dict(
        (
            await session.execute(
                select(Product.slug, Product.id).where(
                    Product.slug.in_([product["slug"] for product in products])
                )
            )
        ).all()
    )
    variants = []
    for product in DEMO_PRODUCTS:
        sizes = product["sizes"] or [""]
        colors = product["colors"] or [""]
        for size in sizes:
            for color in colors:
                variants.append(
                    {
                        "id": uuid4(),
                        "product_id": product_ids[product["slug"]],
                        "size": size,
                        "color": color,
                        "stock": 5,
                    }
                )
    await session.execute(
        _insert_for(session, ProductVariant)
        .values(variants)
        .on_conflict_do_nothing(
            index_elements=[
                ProductVariant.product_id,
                ProductVariant.size,
                ProductVariant.color,
            ]
        )
    )
    await session.execute(
        _insert_for(session, DeliveryMethod)
        .values(
            [
                {"id": uuid4(), **method}
                for method in DELIVERY_METHODS
            ]
        )
        .on_conflict_do_nothing(index_elements=[DeliveryMethod.code])
    )
    await session.execute(
        _insert_for(session, StoreSettings)
        .values(id=1, **STORE_SETTINGS)
        .on_conflict_do_nothing(index_elements=[StoreSettings.id])
    )


async def main() -> None:
    async with SessionFactory.begin() as session:
        await seed_database(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
