import base64
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Time, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.api.dependencies import get_current_user
from app.api.schemas import (
    CategoryOut,
    FavoritePage,
    MessageOut,
    PlaceOut,
    PlacePage,
    ReviewCreate,
    ReviewOut,
    ReviewPage,
    SubmissionCreate,
    SubmissionOut,
)
from app.core.config import get_settings
from app.db.models import (
    Category,
    Favorite,
    Place,
    PlaceStatus,
    Review,
    Submission,
    SubmissionStatus,
    User,
)
from app.db.session import get_db


router = APIRouter(prefix="/api", tags=["Каталог"])

WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)


def _filter_key(
    search: Optional[str],
    category_id: Optional[uuid.UUID],
    district: Optional[str],
    min_rating: Optional[float],
    open_now: bool,
) -> Dict[str, Any]:
    return {
        "search": search.casefold().strip() if search else None,
        "category_id": str(category_id) if category_id else None,
        "district": district.casefold().strip() if district else None,
        "min_rating": min_rating,
        "open_now": open_now,
    }


def _encode_cursor(sort: str, position: Any, place_id: uuid.UUID, filters: Dict[str, Any]) -> str:
    payload = {
        "sort": sort,
        "position": position,
        "id": str(place_id),
        "filters": filters,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str, sort: str, filters: Dict[str, Any]
) -> Tuple[Any, uuid.UUID]:
    try:
        if not cursor or len(cursor) > 2048:
            raise ValueError
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if payload["sort"] != sort or payload["filters"] != filters:
            raise ValueError
        place_id = uuid.UUID(payload["id"])
        if sort == "newest":
            position = datetime.fromisoformat(payload["position"])
        elif sort == "rating":
            position = Decimal(payload["position"])
        else:
            position = str(payload["position"])
        return position, place_id
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Курсор некорректен или не соответствует параметрам фильтрации.",
        ) from error


def _apply_open_now_filter(
    statement: Select[Any],
    now: datetime,
    dialect_name: str = "postgresql",
) -> Select[Any]:
    day_name = WEEKDAYS[now.weekday()]
    local_time = now.time().replace(second=0, microsecond=0)
    if dialect_name == "sqlite":
        intervals = (
            func.json_each(
                func.json_extract(Place.working_hours, f"$.{day_name}")
            )
            .table_valued("value")
            .alias("working_interval")
        )
        opens_at = func.json_extract(intervals.c.value, "$.open")
        closes_at = func.json_extract(intervals.c.value, "$.close")
        current_time: Any = local_time.strftime("%H:%M")
    else:
        intervals = (
            func.jsonb_array_elements(Place.working_hours[day_name])
            .table_valued("value")
            .alias("working_interval")
        )
        opens_at = func.jsonb_extract_path_text(intervals.c.value, "open").cast(Time)
        closes_at = func.jsonb_extract_path_text(intervals.c.value, "close").cast(Time)
        current_time = local_time
    is_open = (
        select(1)
        .select_from(intervals)
        .where(and_(opens_at <= current_time, closes_at > current_time))
        .correlate(Place)
        .exists()
    )
    return statement.where(Place.working_hours.is_not(None), is_open)


def _place_cursor_position(place: Place, sort: str) -> Any:
    if sort == "newest":
        return place.created_at.isoformat()
    if sort == "rating":
        return str(place.rating_cache)
    return place.name.casefold()


def _apply_cursor(
    statement: Select[Any], sort: str, position: Any, place_id: uuid.UUID
) -> Select[Any]:
    if sort == "newest":
        cursor_date = position
        return statement.where(
            or_(
                Place.created_at < cursor_date,
                and_(Place.created_at == cursor_date, Place.id < place_id),
            )
        )
    if sort == "rating":
        return statement.where(
            or_(
                Place.rating_cache < position,
                and_(Place.rating_cache == position, Place.id > place_id),
            )
        )
    return statement.where(
        or_(
            func.lower(Place.name) > position,
            and_(func.lower(Place.name) == position, Place.id > place_id),
        )
    )


@router.get(
    "/categories",
    response_model=List[CategoryOut],
    summary="Получить список категорий",
    description="Возвращает активные категории, включая parent_id для вложенных категорий.",
)
async def list_categories(
    session: AsyncSession = Depends(get_db),
) -> List[Category]:
    result = await session.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.name.asc(), Category.id.asc())
    )
    return list(result.all())


@router.get(
    "/places",
    response_model=PlacePage,
    summary="Найти места в каталоге",
    description=(
        "Публичный список опубликованных мест. Курсорная пагинация keyset: "
        "передавайте next_cursor как cursor, сохраняя исходные фильтры и сортировку. "
        "График работы задаётся локальным временем города: ключи monday–sunday, "
        "значения — массивы интервалов {open, close} в формате HH:MM."
    ),
)
async def list_places(
    search: Optional[str] = Query(default=None, max_length=100, description="Поиск по названию, описанию и адресу."),
    category_id: Optional[uuid.UUID] = Query(default=None, description="Идентификатор категории."),
    district: Optional[str] = Query(default=None, max_length=120, description="Точное название района, без учёта регистра."),
    min_rating: Optional[float] = Query(default=None, ge=0, le=5, description="Минимальный кешированный рейтинг."),
    open_now: bool = Query(default=False, description="Оставить места, открытые по графику прямо сейчас."),
    sort: Literal["newest", "rating", "name"] = Query(
        default="newest",
        description="Порядок: newest (сначала новые), rating (высокий рейтинг), name (по названию).",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None, description="Курсор из next_cursor предыдущей страницы."),
    session: AsyncSession = Depends(get_db),
) -> PlacePage:
    statement = select(Place).where(Place.status == PlaceStatus.PUBLISHED)
    if search:
        escaped = (
            search.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = "%{}%".format(escaped)
        statement = statement.where(
            or_(
                Place.name.ilike(pattern, escape="\\"),
                Place.description.ilike(pattern, escape="\\"),
                Place.address.ilike(pattern, escape="\\"),
            )
        )
    if category_id is not None:
        statement = statement.where(Place.category_id == category_id)
    if district:
        statement = statement.where(
            func.lower(Place.district) == district.strip().casefold()
        )
    if min_rating is not None:
        statement = statement.where(Place.rating_cache >= min_rating)
    if open_now:
        try:
            city_timezone = ZoneInfo(get_settings().city_timezone)
        except ZoneInfoNotFoundError as error:
            raise RuntimeError("В CITY_TIMEZONE указана неизвестная временная зона.") from error
        statement = _apply_open_now_filter(
            statement,
            datetime.now(city_timezone),
            session.get_bind().dialect.name,
        )

    filters = _filter_key(search, category_id, district, min_rating, open_now)
    if cursor:
        position, place_id = _decode_cursor(cursor, sort, filters)
        statement = _apply_cursor(statement, sort, position, place_id)

    if sort == "newest":
        statement = statement.order_by(Place.created_at.desc(), Place.id.desc())
    elif sort == "rating":
        statement = statement.order_by(Place.rating_cache.desc(), Place.id.asc())
    else:
        statement = statement.order_by(func.lower(Place.name).asc(), Place.id.asc())

    rows = list((await session.scalars(statement.limit(limit + 1))).all())
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        next_cursor = _encode_cursor(
            sort,
            _place_cursor_position(last_item, sort),
            last_item.id,
            filters,
        )
    return PlacePage(items=items, next_cursor=next_cursor)


@router.get(
    "/places/{place_id}",
    response_model=PlaceOut,
    summary="Получить карточку места",
    description="Возвращает подробности опубликованного места и его категорию.",
)
async def get_place(
    place_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Place:
    place = await session.scalar(
        select(Place)
        .options(selectinload(Place.category))
        .where(
            Place.id == place_id,
            Place.status == PlaceStatus.PUBLISHED,
        )
    )
    if place is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Место не найдено.")
    return place


@router.get(
    "/favorites",
    response_model=FavoritePage,
    summary="Получить избранные места",
    description="Список избранного текущего пользователя, от новых добавлений к старым.",
)
async def list_favorites(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FavoritePage:
    result = await session.scalars(
        select(Place)
        .join(Favorite, Favorite.place_id == Place.id)
        .where(
            Favorite.user_id == current_user.id,
            Place.status == PlaceStatus.PUBLISHED,
        )
        .order_by(Favorite.created_at.desc(), Place.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return FavoritePage(items=list(result.all()), limit=limit, offset=offset)


@router.put(
    "/favorites/{place_id}",
    response_model=MessageOut,
    summary="Добавить место в избранное",
    description="Повторный запрос безопасен: уже добавленное место останется в избранном.",
)
async def add_favorite(
    place_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageOut:
    place = await session.scalar(
        select(Place.id).where(
            Place.id == place_id,
            Place.status == PlaceStatus.PUBLISHED,
        )
    )
    if place is None:
        raise HTTPException(status_code=404, detail="Опубликованное место не найдено.")

    existing = await session.get(Favorite, (current_user.id, place_id))
    if existing is None:
        session.add(Favorite(user_id=current_user.id, place_id=place_id))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.get(Favorite, (current_user.id, place_id))
            if existing is None:
                raise
    return MessageOut(message="Место добавлено в избранное.")


@router.delete(
    "/favorites/{place_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить место из избранного",
    response_class=Response,
)
async def remove_favorite(
    place_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    favorite = await session.get(Favorite, (current_user.id, place_id))
    if favorite is not None:
        await session.delete(favorite)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/places/{place_id}/reviews",
    response_model=ReviewPage,
    summary="Получить отзывы о месте",
)
async def list_reviews(
    place_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> ReviewPage:
    place_exists = await session.scalar(
        select(Place.id).where(
            Place.id == place_id,
            Place.status == PlaceStatus.PUBLISHED,
        )
    )
    if place_exists is None:
        raise HTTPException(status_code=404, detail="Место не найдено.")
    reviews = await session.execute(
        select(Review, User.first_name, User.username)
        .join(User, User.id == Review.user_id)
        .where(Review.place_id == place_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
    )
    items = [
        ReviewOut(
            id=review.id,
            place_id=review.place_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at,
            user_name=first_name or username,
        )
        for review, first_name, username in reviews.all()
    ]
    return ReviewPage(items=items, limit=limit, offset=offset)


@router.post(
    "/places/{place_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Оставить отзыв",
    description="Один пользователь может оставить только один отзыв на каждое место.",
)
async def create_review(
    place_id: uuid.UUID,
    body: ReviewCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReviewOut:
    place = await session.scalar(
        select(Place)
        .where(
            Place.id == place_id,
            Place.status == PlaceStatus.PUBLISHED,
        )
        .with_for_update()
    )
    if place is None:
        raise HTTPException(status_code=404, detail="Опубликованное место не найдено.")
    existing = await session.scalar(
        select(Review.id).where(
            Review.user_id == current_user.id,
            Review.place_id == place_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Вы уже оставили отзыв на это место.")

    review = Review(
        user_id=current_user.id,
        place_id=place_id,
        rating=body.rating,
        comment=body.comment,
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Вы уже оставили отзыв на это место.",
        ) from error

    aggregate = await session.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.place_id == place_id
        )
    )
    average, count = aggregate.one()
    place.rating_cache = Decimal(str(average)).quantize(Decimal("0.01"))
    place.review_count = count
    await session.commit()
    await session.refresh(review)
    return ReviewOut(
        id=review.id,
        place_id=review.place_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        user_name=current_user.first_name or current_user.username,
    )


@router.post(
    "/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Предложить новое место",
    description=(
        "Создаёт заявку со статусом pending. Заявка не появляется в каталоге "
        "до проверки модератором."
    ),
)
async def create_submission(
    body: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Submission:
    if body.category_id is not None:
        category_exists = await session.scalar(
            select(Category.id).where(
                Category.id == body.category_id,
                Category.is_active.is_(True),
            )
        )
        if category_exists is None:
            raise HTTPException(status_code=422, detail="Активная категория не найдена.")

    submission = Submission(
        submitter_id=current_user.id,
        payload=body.model_dump(mode="json", exclude_none=True),
        status=SubmissionStatus.PENDING,
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)
    return submission
