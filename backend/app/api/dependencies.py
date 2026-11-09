from typing import Any, cast

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.telegram_auth import validate_init_data
from app.db.models import User
from app.db.session import get_db


async def get_current_user(
    init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Проверяет Telegram initData и возвращает пользователя из БД."""
    settings = get_settings()
    try:
        data = validate_init_data(
            init_data=init_data,
            bot_token=settings.bot_token,
            max_age_seconds=settings.init_data_max_age_seconds,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Telegram"},
        ) from error

    telegram_user = cast(dict[str, Any], data["user"])
    telegram_id = telegram_user["id"]
    user = await session.scalar(
        select(User).where(User.telegram_id == telegram_id)
    )

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=telegram_user.get("username"),
            photo_url=telegram_user.get("photo_url"),
            first_name=telegram_user.get("first_name"),
            last_name=telegram_user.get("last_name"),
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            user = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            if user is None:
                raise
    else:
        profile_changed = False
        for field in ("username", "photo_url", "first_name", "last_name"):
            new_value = telegram_user.get(field)
            if getattr(user, field) != new_value:
                setattr(user, field, new_value)
                profile_changed = True
        if profile_changed:
            await session.commit()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись отключена.",
        )
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Разрешает доступ только Telegram ID из ADMIN_IDS."""
    if current_user.telegram_id not in get_settings().admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только администраторам.",
        )
    return current_user
