"""Административные операции с каталогом, заказами и настройками."""
import io
import re
import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin_schemas import (
    AdminDashboardOut,
    AdminCategoryOut,
    AdminCategoryWrite,
    AdminDeliveryOut,
    AdminDeliveryWrite,
    AdminDashboardProduct,
    AdminImageOrder,
    AdminImageOut,
    AdminOrderDetailOut,
    AdminOrderOut,
    AdminOrderPage,
    AdminOrderStatusUpdate,
    AdminProductOut,
    AdminProductPage,
    AdminProductWrite,
    AdminSizeInput,
    AdminSettingsOut,
    AdminSettingsPatch,
    AdminSizeOptionOut,
    AdminSizeOptionWrite,
    AdminVariantOut,
)
from app.api.dependencies import require_admin
from app.api.store import (
    _get_rate,
    _order_detail,
    _order_summary,
)
from app.api.store_schemas import OrderDetailOut
from app.bot.orders import OrderActionError, change_order_status
from app.core.config import get_settings
from app.db.models import (
    Category,
    DeliveryMethod,
    Order,
    Place,
    Product,
    ProductVariant,
    SizeOption,
    StoreSettings,
    User,
)
from app.db.session import get_db


router = APIRouter(
    prefix="/api/admin",
    tags=["Администрирование"],
    dependencies=[Depends(require_admin)],
)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PRODUCT_IMAGES = 20
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def _product_out(product: Product) -> AdminProductOut:
    return AdminProductOut(
        id=product.id,
        title=product.name,
        brand=product.brand,
        description=product.description,
        section=product.section,
        category_id=product.category_id,
        category_name=product.category.name,
        price_byn=(
            product.sale_price_byn
            if product.sale_price_byn is not None
            else product.price_byn
        ),
        old_price_byn=(
            product.price_byn if product.sale_price_byn is not None else None
        ),
        price_rub=(
            product.sale_price_rub
            if product.sale_price_rub is not None
            else product.price_rub
        ),
        old_price_rub=(
            product.price_rub if product.sale_price_rub is not None else None
        ),
        is_new=product.is_new,
        is_active=product.is_active,
        sold_at=product.sold_at,
        images=[
            _image_response(image, index).model_dump()
            for index, image in enumerate(product.photos)
        ],
        variants=[
            AdminVariantOut(
                id=variant.id,
                size=variant.size,
                color=variant.color,
                stock=variant.stock,
            )
            for variant in sorted(
                product.variants,
                key=lambda item: (item.size.casefold(), item.color.casefold()),
            )
        ],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def _load_product(
    session: AsyncSession, product_id: uuid.UUID
) -> Optional[Product]:
    return await session.scalar(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.variants))
        .where(Product.id == product_id)
    )


def _apply_product_payload(
    product: Product,
    payload: AdminProductWrite,
    rate: Decimal,
) -> None:
    product.name = payload.title
    product.brand = payload.brand
    product.description = payload.description
    product.section = payload.section
    product.category_id = payload.category_id
    product.is_new = payload.is_new
    if payload.old_price_byn is not None:
        product.price_byn = payload.old_price_byn
        product.sale_price_byn = payload.price_byn
    else:
        product.price_byn = payload.price_byn
        product.sale_price_byn = None

    if payload.rub_price_mode == "manual":
        current_rub = payload.price_rub
        if current_rub is None:
            raise HTTPException(status_code=422, detail="Для ручного курса укажите цену в RUB.")
        if payload.old_price_byn is not None:
            product.price_rub = payload.old_price_rub or (
                payload.old_price_byn * rate
            ).quantize(Decimal("0.01"))
            if product.price_rub <= current_rub:
                raise HTTPException(
                    status_code=422,
                    detail="Старая цена в RUB должна быть выше текущей. Укажите её вручную.",
                )
            product.sale_price_rub = current_rub
        else:
            product.price_rub = current_rub
            product.sale_price_rub = None
    else:
        product.price_rub = None
        product.sale_price_rub = None

    product.sizes = sorted({item.size for item in payload.sizes})
    product.colors = sorted({item.color for item in payload.sizes if item.color})


async def _replace_product_variants(
    session: AsyncSession,
    product: Product,
    sizes: list[AdminSizeInput],
) -> None:
    requested = [
        (item.size, item.color, item.quantity)
        for item in sizes
    ] or [("", "", 1)]

    existing = {
        (variant.size.casefold(), variant.color.casefold()): variant
        for variant in product.variants
    }
    requested_keys = {(size.casefold(), color.casefold()) for size, color, _ in requested}
    for size, color, quantity in requested:
        key = (size.casefold(), color.casefold())
        variant = existing.get(key)
        if variant is None:
            variant = ProductVariant(
                product_id=product.id,
                size=size,
                color=color,
                stock=quantity,
            )
            session.add(variant)
            product.variants.append(variant)
        else:
            variant.size = size
            variant.color = color
            variant.stock = quantity
    for variant in product.variants:
        if (
            variant.size.casefold(),
            variant.color.casefold(),
        ) not in requested_keys:
            variant.stock = 0


def _slug_for_product() -> str:
    return f"product-{uuid.uuid4().hex}"


def _image_file_paths(uploads_root: Path, image: dict[str, object]) -> list[Path]:
    paths: list[Path] = []
    for key in ("url", "thumbnail_url"):
        value = image.get(key)
        if not isinstance(value, str) or not value.startswith("/uploads/"):
            continue
        relative = value.removeprefix("/uploads/")
        path = (uploads_root / relative).resolve()
        if path.is_relative_to(uploads_root.resolve()):
            paths.append(path)
    return paths


def _remove_image_files(uploads_root: Path, images: list[dict[str, object]]) -> None:
    for image in images:
        for path in _image_file_paths(uploads_root, image):
            path.unlink(missing_ok=True)


def _normalize_image(data: bytes) -> tuple[bytes, bytes]:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(
                    status_code=415,
                    detail="Поддерживаются только изображения JPEG, PNG и WebP.",
                )
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            if image.width * image.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Разрешение изображения слишком велико.")
            if image.width > 1600:
                height = max(1, round(image.height * 1600 / image.width))
                image = image.resize((1600, height), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

            full = io.BytesIO()
            image.save(full, format="WEBP", quality=86, method=6)

            thumbnail = image.copy()
            thumbnail.thumbnail((400, 500), Image.Resampling.LANCZOS)
            thumb_data = io.BytesIO()
            thumbnail.save(thumb_data, format="WEBP", quality=78, method=6)
            return full.getvalue(), thumb_data.getvalue()
    except UnidentifiedImageError as error:
        raise HTTPException(status_code=415, detail="Файл не является изображением.") from error
    except Image.DecompressionBombError as error:
        raise HTTPException(status_code=413, detail="Разрешение изображения слишком велико.") from error
    except OSError as error:
        raise HTTPException(status_code=415, detail="Не удалось прочитать изображение.") from error


def _image_response(image: dict[str, object], index: int) -> AdminImageOut:
    url = image.get("url")
    if not isinstance(url, str) or not url:
        raise HTTPException(
            status_code=500,
            detail="В сохранённой галерее обнаружен некорректный адрес изображения.",
        )
    try:
        image_id = (
            uuid.UUID(str(image.get("id")))
            if image.get("id")
            else uuid.uuid5(uuid.NAMESPACE_URL, url)
        )
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail="В сохранённой галерее обнаружен некорректный ID изображения.",
        ) from error
    thumbnail_url = image.get("thumbnail_url")
    if not isinstance(thumbnail_url, str) or not thumbnail_url:
        thumbnail_url = url
    return AdminImageOut(
        id=image_id,
        url=url,
        thumbnail_url=thumbnail_url,
        alt=str(image.get("alt", "")),
        is_cover=index == 0,
    )


@router.get(
    "/products",
    response_model=AdminProductPage,
    summary="Список товаров для панели администратора",
)
async def admin_list_products(
    search: Optional[str] = Query(default=None, max_length=200),
    category_id: Optional[uuid.UUID] = None,
    product_status: Optional[str] = Query(
        default=None,
        alias="status",
        pattern="^(active|hidden|sold)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> AdminProductPage:
    statement = select(Product)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            Product.name.ilike(pattern) | Product.brand.ilike(pattern)
        )
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if product_status == "active":
        statement = statement.where(Product.is_active.is_(True))
    elif product_status == "hidden":
        statement = statement.where(Product.is_active.is_(False))
    elif product_status == "sold":
        statement = statement.where(Product.sold_at.is_not(None))
    total = int(
        await session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        or 0
    )
    products = await session.scalars(
        statement.options(
            selectinload(Product.category),
            selectinload(Product.variants),
        )
        .order_by(Product.created_at.desc(), Product.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AdminProductPage(
        items=[_product_out(item) for item in products.all()],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/products/{product_id}",
    response_model=AdminProductOut,
    summary="Детали товара для редактирования",
)
async def admin_get_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AdminProductOut:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    return _product_out(product)


@router.get(
    "/dashboard",
    response_model=AdminDashboardOut,
    summary="Сводка заказов, выручки и остатков",
)
async def admin_dashboard(
    session: AsyncSession = Depends(get_db),
) -> AdminDashboardOut:
    timezone_name = get_settings().city_timezone
    local_now = datetime.now(ZoneInfo(timezone_name))
    local_today = datetime.combine(local_now.date(), time.min, tzinfo=local_now.tzinfo)
    local_week = local_today - timedelta(days=local_today.weekday())
    today_start = local_today.astimezone(timezone.utc)
    week_start = local_week.astimezone(timezone.utc)

    pending_orders = int(
        await session.scalar(
            select(func.count()).select_from(Order).where(Order.status == "pending")
        )
        or 0
    )

    async def totals_since(start: datetime) -> tuple[int, Decimal]:
        orders_count, revenue = (
            await session.execute(
                select(
                    func.count(Order.id),
                    func.coalesce(func.sum(Order.total_byn), Decimal("0")),
                ).where(
                    Order.created_at >= start,
                    Order.status != "cancelled",
                )
            )
        ).one()
        return int(orders_count or 0), Decimal(revenue or 0)

    today_orders, today_revenue = await totals_since(today_start)
    week_orders, week_revenue = await totals_since(week_start)

    available_variant_count = (
        select(func.count(ProductVariant.id))
        .where(
            ProductVariant.product_id == Product.id,
            ProductVariant.stock > 0,
        )
        .correlate(Product)
        .scalar_subquery()
    )
    low_stock_products = await session.scalars(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.variants))
        .where(
            Product.is_active.is_(True),
            Product.sold_at.is_(None),
            available_variant_count == 1,
        )
        .order_by(Product.name)
        .limit(30)
    )
    one_size_left = []
    for product in low_stock_products.all():
        remaining = next(
            (variant for variant in product.variants if variant.stock > 0),
            None,
        )
        if remaining is None:
            continue
        one_size_left.append(
            AdminDashboardProduct(
                id=product.id,
                title=product.name,
                category_name=product.category.name,
                stock=remaining.stock,
                image_url=(
                    str(product.photos[0].get("thumbnail_url") or product.photos[0].get("url"))
                    if product.photos
                    else None
                ),
            )
        )

    return AdminDashboardOut(
        pending_orders=pending_orders,
        today_orders=today_orders,
        today_revenue_byn=today_revenue,
        week_orders=week_orders,
        week_revenue_byn=week_revenue,
        one_size_left=one_size_left,
    )


@router.post(
    "/products",
    response_model=AdminProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать товар",
)
async def admin_create_product(
    payload: AdminProductWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminProductOut:
    category = await session.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(status_code=422, detail="Категория не найдена.")
    rate = await _get_rate(session)
    product = Product(
        slug=_slug_for_product(),
        photos=[],
        sizes=[],
        colors=[],
        is_active=True,
        variants=[],
    )
    _apply_product_payload(product, payload, rate)
    session.add(product)
    await session.flush()
    await _replace_product_variants(session, product, payload.sizes)
    await session.commit()
    saved = await _load_product(session, product.id)
    if saved is None:
        raise HTTPException(status_code=500, detail="Созданный товар не найден.")
    return _product_out(saved)


@router.put(
    "/products/{product_id}",
    response_model=AdminProductOut,
    summary="Изменить товар",
)
async def admin_update_product(
    product_id: uuid.UUID,
    payload: AdminProductWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminProductOut:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    if await session.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=422, detail="Категория не найдена.")
    _apply_product_payload(product, payload, await _get_rate(session))
    await _replace_product_variants(session, product, payload.sizes)
    await session.commit()
    saved = await _load_product(session, product_id)
    if saved is None:
        raise HTTPException(status_code=500, detail="Изменённый товар не найден.")
    return _product_out(saved)


@router.patch(
    "/products/{product_id}/visibility",
    response_model=AdminProductOut,
    summary="Скрыть или показать товар",
)
async def admin_set_product_visibility(
    product_id: uuid.UUID,
    is_active: bool = Query(...),
    session: AsyncSession = Depends(get_db),
) -> AdminProductOut:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    product.is_active = is_active
    await session.commit()
    return _product_out(product)


@router.patch(
    "/products/{product_id}/sold",
    response_model=AdminProductOut,
    summary="Отметить товар как проданный",
)
async def admin_mark_product_sold(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AdminProductOut:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    if product.sold_at is None:
        product.sold_at = datetime.now(timezone.utc)
        for variant in product.variants:
            variant.stock = 0
        await session.commit()
    return _product_out(product)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар",
)
async def admin_delete_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    images = list(product.photos)
    uploads_root = get_settings().uploads_path
    await session.delete(product)
    await session.commit()
    _remove_image_files(uploads_root, images)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/products/{product_id}/images",
    response_model=list[AdminImageOut],
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить изображения товара",
)
async def admin_upload_product_images(
    product_id: uuid.UUID,
    files: list[UploadFile] = File(..., min_length=1, max_length=MAX_PRODUCT_IMAGES),
    session: AsyncSession = Depends(get_db),
) -> list[AdminImageOut]:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    if len(product.photos) + len(files) > MAX_PRODUCT_IMAGES:
        raise HTTPException(status_code=422, detail="Для товара можно сохранить не более 20 изображений.")

    uploads_root = get_settings().uploads_path
    product_folder = uploads_root / "products" / str(product.id)
    product_folder.mkdir(parents=True, exist_ok=True)
    new_images: list[dict[str, object]] = []
    created_paths: list[Path] = []
    try:
        for upload in files:
            data = await upload.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Размер одного файла не должен превышать 10 МБ.")
            normalized, thumbnail = _normalize_image(data)
            image_id = uuid.uuid4()
            full_path = product_folder / f"{image_id}.webp"
            thumb_path = product_folder / f"{image_id}.thumb.webp"
            full_path.write_bytes(normalized)
            created_paths.append(full_path)
            thumb_path.write_bytes(thumbnail)
            created_paths.append(thumb_path)
            relative = f"/uploads/products/{product.id}"
            new_images.append(
                {
                    "id": str(image_id),
                    "url": f"{relative}/{image_id}.webp",
                    "thumbnail_url": f"{relative}/{image_id}.thumb.webp",
                    "alt": product.name,
                }
            )
        product.photos = [*product.photos, *new_images]
        await session.commit()
    except Exception:
        await session.rollback()
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise
    return [
        _image_response(image, index)
        for index, image in enumerate(product.photos)
    ]


@router.put(
    "/products/{product_id}/images/order",
    response_model=list[AdminImageOut],
    summary="Изменить порядок изображений и выбрать обложку",
)
async def admin_reorder_product_images(
    product_id: uuid.UUID,
    payload: AdminImageOrder,
    session: AsyncSession = Depends(get_db),
) -> list[AdminImageOut]:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    by_id = {}
    for index, image in enumerate(product.photos):
        image_out = _image_response(image, index)
        by_id[image_out.id] = {
            **image,
            "id": str(image_out.id),
            "thumbnail_url": image_out.thumbnail_url,
        }
    if len(payload.image_ids) != len(by_id) or set(payload.image_ids) != set(by_id):
        raise HTTPException(
            status_code=422,
            detail="Передайте каждый ID изображения товара ровно один раз.",
        )
    product.photos = [by_id[image_id] for image_id in payload.image_ids]
    await session.commit()
    return [
        _image_response(image, index)
        for index, image in enumerate(product.photos)
    ]


@router.delete(
    "/products/{product_id}/images/{image_id}",
    response_model=list[AdminImageOut],
    summary="Удалить изображение товара",
)
async def admin_delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[AdminImageOut]:
    product = await _load_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден.")
    image = next(
        (
            item
            for index, item in enumerate(product.photos)
            if _image_response(item, index).id == image_id
        ),
        None,
    )
    if image is None:
        raise HTTPException(status_code=404, detail="Изображение не найдено.")
    product.photos = [
        item
        for index, item in enumerate(product.photos)
        if _image_response(item, index).id != image_id
    ]
    await session.commit()
    _remove_image_files(get_settings().uploads_path, [image])
    return [
        _image_response(item, index)
        for index, item in enumerate(product.photos)
    ]


@router.get(
    "/categories",
    response_model=list[AdminCategoryOut],
    summary="Список категорий для администратора",
)
async def admin_list_categories(
    session: AsyncSession = Depends(get_db),
) -> list[AdminCategoryOut]:
    categories = await session.scalars(
        select(Category).order_by(Category.group_key, Category.name, Category.id)
    )
    return [AdminCategoryOut.model_validate(item) for item in categories.all()]


@router.post(
    "/categories",
    response_model=AdminCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию",
)
async def admin_create_category(
    payload: AdminCategoryWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminCategoryOut:
    category = Category(**payload.model_dump())
    session.add(category)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Категория с таким slug уже существует.") from error
    await session.refresh(category)
    return AdminCategoryOut.model_validate(category)


@router.put(
    "/categories/{category_id}",
    response_model=AdminCategoryOut,
    summary="Изменить категорию",
)
async def admin_update_category(
    category_id: uuid.UUID,
    payload: AdminCategoryWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminCategoryOut:
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена.")
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Категория с таким slug уже существует.") from error
    await session.refresh(category)
    return AdminCategoryOut.model_validate(category)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить категорию",
)
async def admin_delete_category(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена.")
    products_count = await session.scalar(
        select(func.count()).select_from(Product).where(Product.category_id == category_id)
    )
    child_count = await session.scalar(
        select(func.count()).select_from(Category).where(Category.parent_id == category_id)
    )
    places_count = await session.scalar(
        select(func.count()).select_from(Place).where(Place.category_id == category_id)
    )
    if products_count or child_count or places_count:
        raise HTTPException(
            status_code=409,
            detail="Сначала перенесите товары, места и подкатегории в другую категорию.",
        )
    await session.delete(category)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/size-options",
    response_model=list[AdminSizeOptionOut],
    summary="Список размеров",
)
async def admin_list_size_options(
    group_key: Optional[str] = Query(default=None, pattern="^(clothing|shoes)$"),
    session: AsyncSession = Depends(get_db),
) -> list[AdminSizeOptionOut]:
    statement = select(SizeOption)
    if group_key is not None:
        statement = statement.where(SizeOption.group_key == group_key)
    options = await session.scalars(
        statement.order_by(SizeOption.group_key, SizeOption.sort_order, SizeOption.value)
    )
    return [AdminSizeOptionOut.model_validate(item) for item in options.all()]


@router.post(
    "/size-options",
    response_model=AdminSizeOptionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать размер",
)
async def admin_create_size_option(
    payload: AdminSizeOptionWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminSizeOptionOut:
    option = SizeOption(**payload.model_dump())
    session.add(option)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Такой размер уже есть в этой группе.") from error
    await session.refresh(option)
    return AdminSizeOptionOut.model_validate(option)


@router.put(
    "/size-options/{option_id}",
    response_model=AdminSizeOptionOut,
    summary="Изменить размер",
)
async def admin_update_size_option(
    option_id: uuid.UUID,
    payload: AdminSizeOptionWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminSizeOptionOut:
    option = await session.get(SizeOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail="Размер не найден.")
    for key, value in payload.model_dump().items():
        setattr(option, key, value)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Такой размер уже есть в этой группе.") from error
    await session.refresh(option)
    return AdminSizeOptionOut.model_validate(option)


@router.delete(
    "/size-options/{option_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить размер",
)
async def admin_delete_size_option(
    option_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    option = await session.get(SizeOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail="Размер не найден.")
    await session.delete(option)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/orders",
    response_model=AdminOrderPage,
    summary="Список заказов с фильтром по статусу",
)
async def admin_list_orders(
    order_status: Optional[str] = Query(
        default=None,
        alias="status",
        pattern="^(pending|processing|shipped|completed|cancelled)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> AdminOrderPage:
    statement = select(Order)
    if order_status is not None:
        statement = statement.where(Order.status == order_status)
    total = int(
        await session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        or 0
    )
    orders = list((await session.scalars(
        statement.order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).all())
    users = await session.scalars(
        select(User).where(User.id.in_([order.user_id for order in orders]))
    )
    customer_by_id = {user.id: user for user in users.all()}
    rate = await _get_rate(session)
    result: list[AdminOrderOut] = []
    for order in orders:
        customer = customer_by_id[order.user_id]
        result.append(
            AdminOrderOut(
                order=_order_summary(order, rate),
                customer_telegram_id=customer.telegram_id,
                customer_username=customer.username,
            )
        )
    return AdminOrderPage(items=result, page=page, page_size=page_size, total=total)


async def _admin_order_detail(
    session: AsyncSession, order_id: uuid.UUID
) -> tuple[OrderDetailOut, User]:
    order = await session.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден.")
    customer = await session.get(User, order.user_id)
    if customer is None:
        raise HTTPException(status_code=500, detail="Покупатель заказа не найден.")
    return _order_detail(order, await _get_rate(session)), customer


@router.get(
    "/orders/{order_id}",
    response_model=AdminOrderDetailOut,
    summary="Детали заказа",
)
async def admin_get_order(
    order_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AdminOrderDetailOut:
    order, customer = await _admin_order_detail(session, order_id)
    return AdminOrderDetailOut(
        order=order,
        customer_telegram_id=customer.telegram_id,
        customer_username=customer.username,
    )


@router.patch(
    "/orders/{order_id}/status",
    response_model=AdminOrderDetailOut,
    summary="Изменить статус заказа",
    description="Использует те же переходы статусов, списание и возврат остатков, что и кнопки бота.",
)
async def admin_change_order_status(
    order_id: uuid.UUID,
    payload: AdminOrderStatusUpdate,
    session: AsyncSession = Depends(get_db),
) -> AdminOrderDetailOut:
    try:
        await change_order_status(session, order_id, payload.action)
        await session.commit()
    except OrderActionError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    order, customer = await _admin_order_detail(session, order_id)
    return AdminOrderDetailOut(
        order=order,
        customer_telegram_id=customer.telegram_id,
        customer_username=customer.username,
    )


@router.get(
    "/settings",
    response_model=AdminSettingsOut,
    summary="Получить настройки магазина и способы доставки",
)
async def admin_get_settings(
    session: AsyncSession = Depends(get_db),
) -> AdminSettingsOut:
    store = await session.get(StoreSettings, 1)
    if store is None:
        raise HTTPException(status_code=503, detail="Настройки магазина не заполнены.")
    methods = await session.scalars(
        select(DeliveryMethod).order_by(DeliveryMethod.sort_order, DeliveryMethod.name)
    )
    return AdminSettingsOut(
        manager_username=store.manager_username,
        reviews_url=store.reviews_url,
        store_name=store.store_name,
        welcome_text=store.welcome_text,
        delivery_info_text=store.delivery_info_text,
        how_to_order_steps=store.how_to_order_steps,
        byn_to_rub_rate=store.byn_to_rub_rate,
        deliveries=[AdminDeliveryOut.model_validate(item) for item in methods.all()],
    )


@router.patch(
    "/settings",
    response_model=AdminSettingsOut,
    summary="Изменить настройки магазина",
)
async def admin_update_settings(
    payload: AdminSettingsPatch,
    session: AsyncSession = Depends(get_db),
) -> AdminSettingsOut:
    store = await session.get(StoreSettings, 1)
    if store is None:
        raise HTTPException(status_code=503, detail="Настройки магазина не заполнены.")
    updates = payload.model_dump(exclude_unset=True)
    for required_value in (
        "manager_username",
        "store_name",
        "welcome_text",
        "delivery_info_text",
        "how_to_order_steps",
    ):
        if required_value in updates and updates[required_value] is None:
            raise HTTPException(status_code=422, detail=f"Поле {required_value} не может быть пустым.")
    username = updates.get("manager_username")
    if username is not None and not re.fullmatch(r"@?[A-Za-z0-9_]{5,32}", username):
        raise HTTPException(status_code=422, detail="Некорректный username менеджера.")
    for key, value in updates.items():
        setattr(store, key, str(value) if key == "reviews_url" else value)
    await session.commit()
    return await admin_get_settings(session)


@router.post(
    "/settings/delivery-methods",
    response_model=AdminDeliveryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить способ доставки",
)
async def admin_create_delivery_method(
    payload: AdminDeliveryWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminDeliveryOut:
    method = DeliveryMethod(**payload.model_dump())
    session.add(method)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Способ доставки с таким кодом уже существует.") from error
    await session.refresh(method)
    return AdminDeliveryOut.model_validate(method)


@router.put(
    "/settings/delivery-methods/{method_id}",
    response_model=AdminDeliveryOut,
    summary="Изменить способ доставки",
)
async def admin_update_delivery_method(
    method_id: uuid.UUID,
    payload: AdminDeliveryWrite,
    session: AsyncSession = Depends(get_db),
) -> AdminDeliveryOut:
    method = await session.get(DeliveryMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="Способ доставки не найден.")
    for key, value in payload.model_dump().items():
        setattr(method, key, value)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Способ доставки с таким кодом уже существует.") from error
    await session.refresh(method)
    return AdminDeliveryOut.model_validate(method)


@router.delete(
    "/settings/delivery-methods/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить способ доставки",
)
async def admin_delete_delivery_method(
    method_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    method = await session.get(DeliveryMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="Способ доставки не найден.")
    await session.delete(method)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
