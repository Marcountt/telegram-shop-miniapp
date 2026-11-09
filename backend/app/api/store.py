import re
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.api.store_schemas import (
    CartItemCreate,
    CartItemUpdate,
    CartLineOut,
    CartOut,
    Currency,
    CustomerProfileOut,
    DeliveryMethodOut,
    FavoritePageOut,
    OrderCreate,
    OrderCreatedOut,
    OrderDetailOut,
    OrderLineOut,
    OrderPageOut,
    OrderSummaryOut,
    PreferencesOut,
    PreferencesUpdate,
    ProductCardOut,
    ProductDetailOut,
    ProductGroup,
    ProductPageOut,
    Section,
    StoreCategoryOut,
    StoreSizeOptionOut,
    PublicStoreSettingsOut,
    VariantOut,
)
from app.db.models import (
    CartItem,
    Category,
    DeliveryMethod,
    NotificationOutbox,
    Order as StoreOrder,
    OrderItem,
    Product,
    ProductFavorite,
    ProductVariant,
    StoreSettings,
    SizeOption,
    User,
)
from app.db.session import get_db


router = APIRouter(prefix="/api/store", tags=["Магазин"])
cart_router = APIRouter(prefix="/api/cart", tags=["Корзина"])
orders_router = APIRouter(prefix="/api/orders", tags=["Заказы"])
preferences_router = APIRouter(prefix="/api/me", tags=["Профиль"])
MAX_CART_LINES = 8
MONEY_QUANTUM = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _convert_price(value: Decimal, currency: Currency, rate: Decimal) -> Decimal:
    return _money(value if currency == "BYN" else value * rate)


def _price_in_byn(product: Product, variant: Optional[ProductVariant] = None) -> Decimal:
    if variant is not None and variant.price_byn is not None:
        return variant.price_byn
    if product.sale_price_byn is not None:
        return product.sale_price_byn
    return product.price_byn


def _display_product_price(
    product: Product,
    currency: Currency,
    rate: Decimal,
    *,
    original: bool = False,
    variant: Optional[ProductVariant] = None,
) -> Decimal:
    if variant is not None and variant.price_byn is not None and not original:
        return _convert_price(variant.price_byn, currency, rate)
    if currency == "BYN":
        value = (
            product.price_byn
            if original or product.sale_price_byn is None
            else product.sale_price_byn
        )
        return _convert_price(value, currency, rate)
    if original:
        return (
            _money(product.price_rub)
            if product.price_rub is not None
            else _convert_price(product.price_byn, "RUB", rate)
        )
    if product.sale_price_rub is not None:
        return _money(product.sale_price_rub)
    if product.price_rub is not None and product.sale_price_byn is None:
        return _money(product.price_rub)
    return _convert_price(_price_in_byn(product, variant), currency, rate)


async def _get_rate(session: AsyncSession) -> Decimal:
    rate = await session.scalar(select(StoreSettings.byn_to_rub_rate).where(StoreSettings.id == 1))
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Настройки магазина не заполнены. Запустите сидер.",
        )
    return rate


def _currency(user: User, requested: Optional[Currency]) -> Currency:
    return requested or user.preferred_currency  # type: ignore[return-value]


def _stock_subquery():
    return (
        select(
            ProductVariant.product_id.label("product_id"),
            func.sum(ProductVariant.stock).label("stock"),
        )
        .group_by(ProductVariant.product_id)
        .subquery()
    )


def _product_card(
    product: Product,
    category: Category,
    stock: int,
    currency: Currency,
    rate: Decimal,
) -> ProductCardOut:
    price = _display_product_price(product, currency, rate)
    original = (
        _display_product_price(product, currency, rate, original=True)
        if product.sale_price_byn is not None
        else None
    )
    return ProductCardOut(
        id=product.id,
        category_id=product.category_id,
        category_name=category.name,
        group=category.group_key,
        title=product.name,
        brand=product.brand,
        section=product.section,
        images=product.photos,
        sizes=product.sizes,
        is_new=product.is_new,
        currency=currency,
        price=price,
        original_price=original,
        on_sale=product.sale_price_byn is not None,
        stock=stock,
        sold=product.sold_at is not None or stock == 0,
        created_at=product.created_at,
    )


def _product_conditions(
    *,
    search: Optional[str],
    section: Optional[Section],
    group: Optional[ProductGroup],
    category_id: Optional[uuid.UUID],
    size: Optional[str],
    on_sale: Optional[bool],
    in_stock: Optional[bool],
    min_price: Optional[Decimal],
    max_price: Optional[Decimal],
    currency: Currency,
    rate: Decimal,
):
    conditions = [Product.is_active.is_(True), Category.is_active.is_(True)]
    if search:
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.brand.ilike(pattern, escape="\\"),
            )
        )
    if section == "unisex":
        conditions.append(Product.section == "unisex")
    elif section:
        conditions.append(Product.section.in_([section, "unisex"]))
    if group:
        conditions.append(Category.group_key == group)
    if category_id:
        conditions.append(Product.category_id == category_id)
    if size:
        conditions.append(
            select(ProductVariant.id)
            .where(
                ProductVariant.product_id == Product.id,
                func.lower(ProductVariant.size) == size.casefold(),
            )
            .exists()
        )
    if on_sale is True:
        conditions.append(Product.sale_price_byn.is_not(None))
    if in_stock:
        conditions.append(
            select(ProductVariant.id)
            .where(ProductVariant.product_id == Product.id, ProductVariant.stock > 0)
            .exists()
        )

    effective_price_byn = case(
        (Product.sale_price_byn.is_not(None), Product.sale_price_byn),
        else_=Product.price_byn,
    )
    if currency == "BYN":
        currency_price = effective_price_byn
    else:
        currency_price = case(
            (Product.sale_price_rub.is_not(None), Product.sale_price_rub),
            (Product.price_rub.is_not(None), Product.price_rub),
            else_=effective_price_byn * rate,
        )
    if min_price is not None:
        conditions.append(currency_price >= min_price)
    if max_price is not None:
        conditions.append(currency_price <= max_price)
    return conditions


async def _cart_rows(session: AsyncSession, user_id: uuid.UUID):
    result = await session.execute(
        select(CartItem, ProductVariant, Product)
        .join(ProductVariant, ProductVariant.id == CartItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at, CartItem.id)
    )
    return list(result.all())


async def _cart_response(
    session: AsyncSession, user: User, currency: Currency, rate: Decimal
) -> CartOut:
    lines: list[CartLineOut] = []
    subtotal = Decimal("0")
    for item, variant, product in await _cart_rows(session, user.id):
        unit_price = _display_product_price(
            product, currency, rate, variant=variant
        )
        line_total = _money(unit_price * item.quantity)
        subtotal += line_total
        lines.append(
            CartLineOut(
                variant_id=variant.id,
                product_id=product.id,
                title=product.name,
                image=product.photos[0] if product.photos else None,
                size=variant.size,
                color=variant.color,
                quantity=item.quantity,
                stock=variant.stock,
                currency=currency,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
    return CartOut(
        items=lines,
        currency=currency,
        items_total=_money(subtotal),
        item_count=sum(line.quantity for line in lines),
    )


def _order_summary(order: StoreOrder, rate: Decimal) -> OrderSummaryOut:
    currency: Currency = order.currency  # type: ignore[assignment]
    return OrderSummaryOut(
        id=order.id,
        status=order.status,
        recipient_name=order.recipient_name,
        phone=order.phone,
        delivery_method_name=order.delivery_method_name,
        city=order.city,
        delivery_address=order.delivery_address,
        currency=currency,
        items_total=_convert_price(order.items_total_byn, currency, rate),
        total=_convert_price(order.total_byn, currency, rate),
        created_at=order.created_at,
    )


def _order_detail(order: StoreOrder, rate: Decimal) -> OrderDetailOut:
    currency: Currency = order.currency  # type: ignore[assignment]
    return OrderDetailOut(
        **_order_summary(order, rate).model_dump(),
        delivery_price=(
            _convert_price(order.delivery_price_byn, currency, rate)
            if order.delivery_price_byn is not None
            else None
        ),
        delivery_price_note=order.delivery_price_note,
        comment=order.comment,
        items=[
            OrderLineOut(
                product_id=item.product_id,
                product_name=item.product_name,
                size=item.size,
                color=item.color,
                quantity=item.quantity,
                currency=currency,
                unit_price=_convert_price(item.unit_price_byn, currency, rate),
                line_total=_convert_price(
                    item.unit_price_byn * item.quantity, currency, rate
                ),
            )
            for item in order.items
        ],
    )


def _manager_message(order: StoreOrder, rate: Decimal) -> str:
    currency = order.currency
    currency_total = _convert_price(order.total_byn, currency, rate)
    item_lines = [
        f"- {item.product_name[:24]} {item.size[:8]}/{item.color[:8]} x{item.quantity}"
        for item in order.items
    ]
    location = order.delivery_address
    message = (
        f"Заказ BRAND GRODNO #{str(order.id)[:8]}\n"
        f"Товары: {'; '.join(item_lines)}\n"
        f"Сумма: {currency_total} {currency}\n"
        f"Доставка: {order.delivery_method_name[:30]}, {order.city[:60]}, {location[:150]}"
        f"{f' ({order.delivery_price_note})' if order.delivery_price_note else ''}\n"
        f"Получатель: {order.recipient_name}\n"
        f"Телефон: {order.phone}"
    )
    if order.comment:
        message += f"\nКомментарий: {order.comment}"
    return message[:1000]


async def _load_order(
    session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[StoreOrder]:
    return await session.scalar(
        select(StoreOrder)
        .options(selectinload(StoreOrder.items))
        .where(StoreOrder.id == order_id, StoreOrder.user_id == user_id)
    )


@router.get(
    "/categories",
    response_model=list[StoreCategoryOut],
    summary="Категории товаров по группе",
)
async def list_store_categories(
    group: Optional[ProductGroup] = Query(default=None, description="Группа каталога: clothing или shoes."),
    session: AsyncSession = Depends(get_db),
) -> list[Category]:
    statement = select(Category).where(Category.is_active.is_(True))
    if group:
        statement = statement.where(Category.group_key == group)
    result = await session.scalars(statement.order_by(Category.group_key, Category.name))
    return list(result.all())


@router.get(
    "/sizes",
    response_model=list[StoreSizeOptionOut],
    summary="Доступные размеры для фильтров каталога",
)
async def list_store_sizes(
    group: ProductGroup = Query(..., description="Группа каталога: clothing или shoes."),
    session: AsyncSession = Depends(get_db),
) -> list[SizeOption]:
    result = await session.scalars(
        select(SizeOption)
        .where(SizeOption.group_key == group, SizeOption.is_active.is_(True))
        .order_by(SizeOption.sort_order, SizeOption.value)
    )
    return list(result.all())


@router.get(
    "/products",
    response_model=ProductPageOut,
    summary="Каталог товаров с фильтрами и пагинацией",
    description=(
        "Поиск по названию и бренду; фильтры section, group, category_id, size, "
        "ценовой диапазон в выбранной валюте, sale и stock. Секции men/women "
        "также включают unisex. Порядок: newest, price_desc, price_asc. "
        "Sold-out товары остаются в выдаче и отмечаются sold=true."
    ),
)
async def list_products(
    search: Optional[str] = Query(default=None, max_length=100),
    section: Optional[Section] = Query(default=None),
    group: Optional[ProductGroup] = Query(default=None),
    category_id: Optional[uuid.UUID] = Query(default=None),
    size: Optional[str] = Query(default=None, min_length=1, max_length=40),
    min_price: Optional[Decimal] = Query(default=None, ge=0),
    max_price: Optional[Decimal] = Query(default=None, ge=0),
    on_sale: Optional[bool] = Query(default=None),
    in_stock: Optional[bool] = Query(default=None),
    currency: Optional[Currency] = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|price_desc|price_asc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProductPageOut:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price не может превышать max_price.")
    selected_currency = _currency(user, currency)
    rate = await _get_rate(session)
    conditions = _product_conditions(
        search=search,
        section=section,
        group=group,
        category_id=category_id,
        size=size,
        on_sale=on_sale,
        in_stock=in_stock,
        min_price=min_price,
        max_price=max_price,
        currency=selected_currency,
        rate=rate,
    )
    stock = _stock_subquery()
    statement = (
        select(Product, Category, func.coalesce(stock.c.stock, 0).label("stock"))
        .join(Category, Category.id == Product.category_id)
        .outerjoin(stock, stock.c.product_id == Product.id)
        .where(*conditions)
    )
    count = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    effective_price_byn = case(
        (Product.sale_price_byn.is_not(None), Product.sale_price_byn),
        else_=Product.price_byn,
    )
    effective_price = (
        effective_price_byn
        if selected_currency == "BYN"
        else case(
            (Product.sale_price_rub.is_not(None), Product.sale_price_rub),
            (Product.price_rub.is_not(None), Product.price_rub),
            else_=effective_price_byn * rate,
        )
    )
    if sort == "price_desc":
        statement = statement.order_by(effective_price.desc(), Product.id)
    elif sort == "price_asc":
        statement = statement.order_by(effective_price.asc(), Product.id)
    else:
        statement = statement.order_by(Product.created_at.desc(), Product.id.desc())
    rows = (
        await session.execute(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    total = int(count or 0)
    return ProductPageOut(
        items=[
            _product_card(product, category, int(stock_count), selected_currency, rate)
            for product, category, stock_count in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
        currency=selected_currency,
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductDetailOut,
    summary="Карточка товара с вариантами и остатками",
)
async def get_product(
    product_id: uuid.UUID,
    currency: Optional[Currency] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProductDetailOut:
    selected_currency = _currency(user, currency)
    rate = await _get_rate(session)
    product = await session.scalar(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.variants))
        .where(Product.id == product_id, Product.is_active.is_(True))
    )
    if product is None or not product.category.is_active:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    stock = sum(variant.stock for variant in product.variants)
    card = _product_card(product, product.category, stock, selected_currency, rate)
    return ProductDetailOut(
        **card.model_dump(exclude={"sizes"}),
        description=product.description,
        sizes=sorted({variant.size for variant in product.variants if variant.size}),
        colors=sorted({variant.color for variant in product.variants if variant.color}),
        variants=[
            VariantOut(
                id=variant.id,
                size=variant.size,
                color=variant.color,
                stock=variant.stock,
                currency=selected_currency,
                price=_display_product_price(
                    product, selected_currency, rate, variant=variant
                ),
            )
            for variant in sorted(
                product.variants, key=lambda value: (value.size, value.color)
            )
        ],
    )


@preferences_router.get(
    "", response_model=CustomerProfileOut, summary="Получить профиль покупателя"
)
async def get_customer_profile(
    user: User = Depends(get_current_user),
) -> CustomerProfileOut:
    return CustomerProfileOut(
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url,
        preferred_section=user.preferred_section,
        preferred_currency=user.preferred_currency,
        is_admin=user.telegram_id in get_settings().admin_ids,
    )


@preferences_router.get(
    "/preferences", response_model=PreferencesOut, summary="Получить настройки каталога пользователя"
)
async def get_preferences(user: User = Depends(get_current_user)) -> PreferencesOut:
    return PreferencesOut(section=user.preferred_section, currency=user.preferred_currency)


@preferences_router.put(
    "/preferences", response_model=PreferencesOut, summary="Сохранить секцию и валюту каталога"
)
async def update_preferences(
    payload: PreferencesUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    if payload.section is not None:
        user.preferred_section = payload.section
    if payload.currency is not None:
        user.preferred_currency = payload.currency
    await session.commit()
    await session.refresh(user)
    return PreferencesOut(section=user.preferred_section, currency=user.preferred_currency)


@router.get(
    "/favorites", response_model=FavoritePageOut, summary="Список избранных товаров"
)
async def list_product_favorites(
    currency: Optional[Currency] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FavoritePageOut:
    selected_currency = _currency(user, currency)
    rate = await _get_rate(session)
    statement = (
        select(Product, Category)
        .join(ProductFavorite, ProductFavorite.product_id == Product.id)
        .join(Category, Category.id == Product.category_id)
        .where(ProductFavorite.user_id == user.id, Product.is_active.is_(True))
    )
    total = int(
        await session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        or 0
    )
    rows = (
        await session.execute(
            statement.order_by(ProductFavorite.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items: list[ProductCardOut] = []
    for product, category in rows:
        stock = int(
            await session.scalar(
                select(func.coalesce(func.sum(ProductVariant.stock), 0)).where(
                    ProductVariant.product_id == product.id
                )
            )
            or 0
        )
        items.append(_product_card(product, category, stock, selected_currency, rate))
    return FavoritePageOut(
        items=items, page=page, page_size=page_size, total=total, currency=selected_currency
    )


@router.put(
    "/favorites/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Добавить товар в избранное",
)
async def add_product_favorite(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    exists = await session.scalar(
        select(Product.id).where(Product.id == product_id, Product.is_active.is_(True))
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    favorite_insert = (
        sqlite_insert(ProductFavorite)
        if session.get_bind().dialect.name == "sqlite"
        else postgresql_insert(ProductFavorite)
    )
    await session.execute(
        favorite_insert
        .values(user_id=user.id, product_id=product_id)
        .on_conflict_do_nothing(
            index_elements=[ProductFavorite.user_id, ProductFavorite.product_id]
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/favorites/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар из избранного",
)
async def remove_product_favorite(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await session.execute(
        delete(ProductFavorite).where(
            ProductFavorite.user_id == user.id,
            ProductFavorite.product_id == product_id,
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@cart_router.get("", response_model=CartOut, summary="Получить корзину и сумму")
async def get_cart(
    currency: Optional[Currency] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CartOut:
    return await _cart_response(
        session, user, _currency(user, currency), await _get_rate(session)
    )


@cart_router.post(
    "/items", response_model=CartOut, summary="Добавить вариант товара в корзину"
)
async def add_cart_item(
    payload: CartItemCreate,
    currency: Optional[Currency] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CartOut:
    variant = await session.scalar(
        select(ProductVariant)
        .where(ProductVariant.id == payload.variant_id)
        .with_for_update()
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="Вариант товара не найден.")
    product = await session.get(Product, variant.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=404, detail="Товар недоступен.")
    item = await session.scalar(
        select(CartItem)
        .where(CartItem.user_id == user.id, CartItem.variant_id == variant.id)
        .with_for_update()
    )
    new_quantity = payload.quantity + (item.quantity if item else 0)
    if new_quantity > 99:
        raise HTTPException(
            status_code=422,
            detail="Количество одного варианта не может превышать 99.",
        )
    if variant.stock < new_quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Недостаточно товара на складе. Доступно: {variant.stock}.",
        )
    if item is None:
        line_count = int(
            await session.scalar(
                select(func.count()).select_from(CartItem).where(CartItem.user_id == user.id)
            )
            or 0
        )
        if line_count >= MAX_CART_LINES:
            raise HTTPException(
                status_code=409,
                detail=f"Корзина может содержать не более {MAX_CART_LINES} вариантов.",
            )
        session.add(CartItem(user_id=user.id, variant_id=variant.id, quantity=new_quantity))
    else:
        item.quantity = new_quantity
    await session.commit()
    return await _cart_response(
        session, user, _currency(user, currency), await _get_rate(session)
    )


@cart_router.patch(
    "/items/{variant_id}", response_model=CartOut, summary="Изменить количество товара в корзине"
)
async def update_cart_item(
    variant_id: uuid.UUID,
    payload: CartItemUpdate,
    currency: Optional[Currency] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CartOut:
    variant = await session.scalar(
        select(ProductVariant).where(ProductVariant.id == variant_id).with_for_update()
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="Вариант товара не найден.")
    item = await session.scalar(
        select(CartItem).where(
            CartItem.user_id == user.id, CartItem.variant_id == variant_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Товара нет в корзине.")
    if payload.quantity > variant.stock:
        raise HTTPException(
            status_code=409,
            detail=f"Недостаточно товара на складе. Доступно: {variant.stock}.",
        )
    item.quantity = payload.quantity
    await session.commit()
    return await _cart_response(
        session, user, _currency(user, currency), await _get_rate(session)
    )


@cart_router.delete(
    "/items/{variant_id}", response_model=CartOut, summary="Удалить товар из корзины"
)
async def remove_cart_item(
    variant_id: uuid.UUID,
    currency: Optional[Currency] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CartOut:
    await session.execute(
        delete(CartItem).where(
            CartItem.user_id == user.id, CartItem.variant_id == variant_id
        )
    )
    await session.commit()
    return await _cart_response(
        session, user, _currency(user, currency), await _get_rate(session)
    )


@orders_router.post(
    "", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED,
    summary="Оформить заказ из корзины",
    description=(
        "Для курьера обязателен полный адрес. Для остальных способов нужны город "
        "и отделение либо адрес. Наличие проверяется при оформлении, а остатки "
        "списываются транзакционно при подтверждении заказа менеджером. "
        "Корзина очищается только после успешного оформления."
    ),
)
async def create_order(
    payload: OrderCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderCreatedOut:
    rate = await _get_rate(session)
    currency = _currency(user, None)
    store_settings = await session.get(StoreSettings, 1)
    if store_settings is None:
        raise HTTPException(status_code=503, detail="Настройки магазина не заполнены.")
    manager_username = store_settings.manager_username.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", manager_username):
        raise HTTPException(status_code=503, detail="Некорректный username менеджера в настройках.")

    delivery = await session.scalar(
        select(DeliveryMethod).where(
            DeliveryMethod.id == payload.delivery_method_id,
            DeliveryMethod.is_active.is_(True),
        )
    )
    if delivery is None:
        raise HTTPException(status_code=422, detail="Выбранный способ доставки недоступен.")
    is_courier = delivery.code.casefold() == "courier"
    if is_courier and not payload.address:
        raise HTTPException(status_code=422, detail="Для курьера укажите полный адрес.")
    if not is_courier and not (payload.address or payload.branch):
        raise HTTPException(
            status_code=422, detail="Укажите адрес или отделение доставки."
        )
    delivery_address = (
        f"Адрес: {payload.address}; отделение: {payload.branch}"
        if payload.address and payload.branch
        else payload.address or f"Отделение: {payload.branch}"
    )
    cart_rows = await session.execute(
        select(CartItem, ProductVariant, Product)
        .join(ProductVariant, ProductVariant.id == CartItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(CartItem.user_id == user.id)
        .order_by(ProductVariant.id)
        .with_for_update(of=[CartItem, ProductVariant])
    )
    rows = list(cart_rows.all())
    if not rows:
        raise HTTPException(status_code=409, detail="Корзина пуста.")
    if len(rows) > MAX_CART_LINES:
        raise HTTPException(status_code=409, detail="В корзине слишком много вариантов.")

    items_total = Decimal("0")
    order_lines: list[tuple[CartItem, ProductVariant, Product, Decimal]] = []
    for cart_item, variant, product in rows:
        if not product.is_active:
            raise HTTPException(status_code=409, detail=f"Товар «{product.name}» недоступен.")
        if variant.stock < cart_item.quantity:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Недостаточно товара «{product.name}» размера {variant.size}. "
                    f"Доступно: {variant.stock}."
                ),
            )
        unit_price = _price_in_byn(product, variant)
        items_total += unit_price * cart_item.quantity
        order_lines.append((cart_item, variant, product, unit_price))
    items_total = _money(items_total)
    delivery_price = delivery.price_byn or Decimal("0")
    total = _money(items_total + delivery_price)
    order = StoreOrder(
        user_id=user.id,
        recipient_name=payload.recipient_name,
        phone=payload.phone,
        delivery_method_name=delivery.name,
        delivery_method_code=delivery.code,
        delivery_price_byn=delivery.price_byn,
        delivery_price_note=delivery.price_note,
        city=payload.city,
        delivery_address=delivery_address,
        comment=payload.comment,
        currency=currency,
        items_total_byn=items_total,
        total_byn=total,
    )
    session.add(order)
    await session.flush()
    for cart_item, variant, product, unit_price in order_lines:
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                variant_id=variant.id,
                product_name=product.name,
                size=variant.size,
                color=variant.color,
                quantity=cart_item.quantity,
                unit_price_byn=unit_price,
            )
        )
        await session.delete(cart_item)
    session.add(
        NotificationOutbox(
            event_type="new_order",
            payload={"order_id": str(order.id), "delivered_to": []},
        )
    )
    await session.commit()
    saved_order = await _load_order(session, order.id, user.id)
    if saved_order is None:
        raise HTTPException(status_code=500, detail="Созданный заказ не найден.")
    message = _manager_message(saved_order, rate)
    manager_link = (
        f"https://t.me/{quote(manager_username, safe='')}?text={quote(message, safe='')}"
    )
    return OrderCreatedOut(order=_order_detail(saved_order, rate), manager_link=manager_link)


@orders_router.get("", response_model=OrderPageOut, summary="Список моих покупок")
async def list_my_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderPageOut:
    total = int(
        await session.scalar(
            select(func.count()).select_from(StoreOrder).where(StoreOrder.user_id == user.id)
        )
        or 0
    )
    orders = await session.scalars(
        select(StoreOrder)
        .where(StoreOrder.user_id == user.id)
        .order_by(StoreOrder.created_at.desc(), StoreOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rate = await _get_rate(session)
    return OrderPageOut(
        items=[_order_summary(order, rate) for order in orders.all()],
        page=page,
        page_size=page_size,
        total=total,
    )


@orders_router.get(
    "/{order_id}", response_model=OrderDetailOut, summary="Детали моей покупки"
)
async def get_my_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderDetailOut:
    order = await _load_order(session, order_id, user.id)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден.")
    return _order_detail(order, await _get_rate(session))


@router.get(
    "/settings",
    response_model=PublicStoreSettingsOut,
    summary="Публичные настройки магазина и способы доставки",
)
async def get_public_store_settings(
    currency: Currency = Query(default="BYN"),
    session: AsyncSession = Depends(get_db),
) -> PublicStoreSettingsOut:
    settings = await session.get(StoreSettings, 1)
    if settings is None:
        raise HTTPException(status_code=503, detail="Настройки магазина не заполнены.")
    rate = settings.byn_to_rub_rate
    methods = await session.scalars(
        select(DeliveryMethod)
        .where(DeliveryMethod.is_active.is_(True))
        .order_by(DeliveryMethod.sort_order, DeliveryMethod.name)
    )
    return PublicStoreSettingsOut(
        manager_username=settings.manager_username,
        reviews_url=settings.reviews_url,
        store_name=settings.store_name,
        currency=currency,
        delivery_methods=[
            DeliveryMethodOut(
                id=method.id,
                code=method.code,
                name=method.name,
                currency=currency,
                price=(
                    _convert_price(method.price_byn, currency, rate)
                    if method.price_byn is not None
                    else None
                ),
                price_note=method.price_note,
            )
            for method in methods.all()
        ],
    )


@router.get(
    "/delivery-methods",
    response_model=list[DeliveryMethodOut],
    summary="Активные способы доставки и цены",
)
async def list_delivery_methods(
    currency: Currency = Query(default="BYN"),
    session: AsyncSession = Depends(get_db),
) -> list[DeliveryMethodOut]:
    settings = await session.get(StoreSettings, 1)
    if settings is None:
        raise HTTPException(status_code=503, detail="Настройки магазина не заполнены.")
    methods = await session.scalars(
        select(DeliveryMethod)
        .where(DeliveryMethod.is_active.is_(True))
        .order_by(DeliveryMethod.sort_order, DeliveryMethod.name)
    )
    return [
        DeliveryMethodOut(
            id=method.id,
            code=method.code,
            name=method.name,
            currency=currency,
            price=(
                _convert_price(method.price_byn, currency, settings.byn_to_rub_rate)
                if method.price_byn is not None
                else None
            ),
            price_note=method.price_note,
        )
        for method in methods.all()
    ]
