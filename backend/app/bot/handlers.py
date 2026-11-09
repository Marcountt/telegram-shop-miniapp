"""Команды, меню и обработчики статусов заказов."""
import logging
import re
import uuid
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.notifications import _order_keyboard
from app.bot.orders import (
    STATUS_LABELS,
    OrderActionError,
    change_order_status,
)
from app.core.config import get_settings
from app.db.models import DeliveryMethod, Order, StoreSettings, User
from app.db.session import SessionFactory


logger = logging.getLogger(__name__)
router = Router(name="store")


def _delivery_price(method: DeliveryMethod) -> str:
    if method.price_byn is not None:
        return f"{method.price_byn:.2f} BYN"
    return method.price_note or "по договорённости"


def _manager_url(username: str) -> Optional[str]:
    username = username.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        logger.error("В настройках магазина указан некорректный username менеджера.")
        return None
    return f"https://t.me/{username}"


def _admin_app_url(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["admin"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def _welcome_data() -> Optional[tuple[str, InlineKeyboardMarkup]]:
    async with SessionFactory() as session:
        store = await session.get(StoreSettings, 1)
        if store is None:
            return None
        deliveries = list(
            (
                await session.scalars(
                    select(DeliveryMethod)
                    .where(DeliveryMethod.is_active.is_(True))
                    .order_by(DeliveryMethod.sort_order, DeliveryMethod.name)
                )
            ).all()
        )
        lines = [
            store.store_name,
            "",
            store.welcome_text,
            "",
            "Как заказать:",
        ]
        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(store.how_to_order_steps, start=1)
        )
        lines.extend(["", "Доставка:"])
        lines.extend(
            f"• {method.name} — {_delivery_price(method)}" for method in deliveries
        )
        builder = [
            [
                InlineKeyboardButton(
                    text="🛍 Открыть каталог",
                    web_app=WebAppInfo(url=get_settings().mini_app_url),
                )
            ]
        ]
        extra: list[InlineKeyboardButton] = [
            InlineKeyboardButton(text="Информация о доставке", callback_data="delivery_info")
        ]
        if store.reviews_url.startswith(("https://", "http://")):
            extra.append(
                InlineKeyboardButton(text="Отзывы", url=store.reviews_url)
            )
        manager_url = _manager_url(store.manager_username)
        if manager_url:
            extra.append(
                InlineKeyboardButton(text="Связаться с менеджером", url=manager_url)
            )
        builder.append(extra)
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=builder)


@router.message(CommandStart())
async def start(message: Message) -> None:
    welcome = await _welcome_data()
    if welcome is None:
        logger.error("Настройки магазина не найдены; запустите сидер.")
        await message.answer("Магазин временно недоступен. Попробуйте позже.")
        return
    await message.answer(welcome[0], reply_markup=welcome[1])


@router.callback_query(F.data == "delivery_info")
async def delivery_info(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        store = await session.get(StoreSettings, 1)
    if store is None:
        await callback.answer("Информация о доставке пока недоступна.", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(store.delivery_info_text)


@router.message(Command("orders"))
async def orders(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя Telegram.")
        return
    async with SessionFactory() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        if user is None:
            await message.answer("У вас пока нет заказов.")
            return
        user_orders = list(
            (
                await session.scalars(
                    select(Order)
                    .options(selectinload(Order.items))
                    .where(Order.user_id == user.id)
                    .order_by(Order.created_at.desc(), Order.id.desc())
                    .limit(10)
                )
            ).all()
        )
    if not user_orders:
        await message.answer("У вас пока нет заказов.")
        return
    lines = ["Ваши последние заказы:"]
    for order in user_orders:
        lines.extend(
            [
                "",
                f"№{str(order.id)[:8]} — {STATUS_LABELS.get(order.status, order.status)}",
                f"{order.total_byn:.2f} BYN · {order.delivery_method_name}",
            ]
        )
    await message.answer("\n".join(lines))


@router.message(Command("admin"))
async def admin(message: Message) -> None:
    settings = get_settings()
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        await message.answer("Эта команда доступна только администраторам.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть панель магазина",
                    web_app=WebAppInfo(url=_admin_app_url(settings.mini_app_url)),
                )
            ]
        ]
    )
    await message.answer("Панель администратора магазина:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("order:"))
async def order_action(callback: CallbackQuery) -> None:
    settings = get_settings()
    if callback.from_user.id not in settings.privileged_ids:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Некорректное действие.", show_alert=True)
        return
    try:
        order_id = uuid.UUID(parts[1])
        async with SessionFactory.begin() as session:
            order = await change_order_status(session, order_id, parts[2])
            status_label = STATUS_LABELS[order.status]
            updated_status = order.status
    except (ValueError, OrderActionError) as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.answer(f"Статус заказа: {status_label}.")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=_order_keyboard(order_id, updated_status)
            )
        except TelegramAPIError:
            logger.exception("Не удалось обновить кнопки заказа %s.", order_id)
