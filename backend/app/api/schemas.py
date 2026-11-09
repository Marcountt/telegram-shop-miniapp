from datetime import datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryOut(APIModel):
    id: UUID
    parent_id: Optional[UUID]
    name: str
    slug: str
    description: Optional[str]


class WorkingInterval(APIModel):
    """Интервал работы в локальном времени: 24-часовой формат HH:MM."""

    open: time = Field(description="Время открытия, например 09:00.")
    close: time = Field(description="Время закрытия, например 18:00.")

    @field_validator("open", "close")
    @classmethod
    def reject_seconds(cls, value: time) -> time:
        if value.second or value.microsecond:
            raise ValueError("Указывайте время с точностью до минуты.")
        return value

    @field_validator("close")
    @classmethod
    def close_after_open(cls, value: time, info: Any) -> time:
        open_time = info.data.get("open")
        if open_time is not None and value <= open_time:
            raise ValueError("Время закрытия должно быть позже времени открытия.")
        return value


class PhotoItem(APIModel):
    url: HttpUrl
    alt: Optional[str] = None


class PlaceSummary(APIModel):
    id: UUID
    category_id: Optional[UUID]
    name: str
    address: Optional[str]
    district: Optional[str]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    photos: List[Dict[str, Any]]
    rating_cache: Decimal
    review_count: int


class PlaceOut(PlaceSummary):
    description: Optional[str]
    phone: Optional[str]
    telegram: Optional[str]
    website: Optional[str]
    working_hours: Optional[Dict[str, List[WorkingInterval]]]
    status: str
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryOut] = None


class PlacePage(APIModel):
    items: List[PlaceSummary]
    next_cursor: Optional[str] = Field(
        description="Курсор для следующей страницы; null, если результатов больше нет."
    )


class ReviewCreate(APIModel):
    rating: int = Field(ge=1, le=5, description="Оценка от 1 до 5 звёзд.")
    comment: Optional[str] = Field(default=None, max_length=5000)


class ReviewOut(APIModel):
    id: UUID
    place_id: UUID
    rating: int
    comment: Optional[str]
    created_at: datetime
    user_name: Optional[str] = None


class ReviewPage(APIModel):
    items: List[ReviewOut]
    limit: int
    offset: int


class FavoritePage(APIModel):
    items: List[PlaceSummary]
    limit: int
    offset: int


class SubmissionCreate(APIModel):
    category_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=300)
    district: Optional[str] = Field(default=None, max_length=120)
    latitude: Optional[Decimal] = Field(default=None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(default=None, ge=-180, le=180)
    phone: Optional[str] = Field(default=None, max_length=32)
    telegram: Optional[str] = Field(default=None, max_length=64)
    website: Optional[HttpUrl] = None
    working_hours: Optional[Dict[str, List[WorkingInterval]]] = None
    photos: List[PhotoItem] = Field(default_factory=list, max_length=20)

    @field_validator("working_hours")
    @classmethod
    def validate_weekday_names(
        cls, value: Optional[Dict[str, List[WorkingInterval]]]
    ) -> Optional[Dict[str, List[WorkingInterval]]]:
        if value is not None:
            allowed = {
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday",
            }
            unknown_days = set(value) - allowed
            if unknown_days:
                raise ValueError(
                    "Неизвестный день недели: {}".format(", ".join(sorted(unknown_days)))
                )
        return value


class SubmissionOut(APIModel):
    id: UUID
    place_id: Optional[UUID]
    status: str
    created_at: datetime


class MessageOut(APIModel):
    message: str
