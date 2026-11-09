"""Доставка событий из transactional outbox в Telegram."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot.orders import STATUS_LABELS
from app.core.config import get_settings
from app.db.models import NotificationOutbox, Order, User
from app.db.session import SessionFactory


logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 2
MAX_BACKOFF_SECONDS = 300


def _order_keyboard(order_id: uuid.UUID, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "pending":
        builder.button(text="✅ Подтвердить", callback_data=f"order:{order_id}:confirm")
        builder.button(text="❌ Отменить", callback_data=f"order:{order_id}:cancel")
    elif status == "processing":
        builder.button(text="📦 Отправлен", callback_data=f"order:{order_id}:shipped")
        builder.button(text="❌ Отменить", callback_data=f"order:{order_id}:cancel")
    elif status == "shipped":
        builder.button(text="✅ Доставлен", callback_data=f"order:{order_id}:delivered")
    builder.adjust(2)
    return builder.as_markup()


def _format_manager_order(order: Order, user: User) -> str:
    lines = [
        f"🛍 Новый заказ №{str(order.id)[:8]}",
        f"Статус: {STATUS_LABELS[order.status]}",
        f"Покупатель: {order.recipient_name}",
        f"Telegram ID: {user.telegram_id}",
        f"Телефон: {order.phone}",
        f"Доставка: {order.delivery_method_name}",
        f"Город: {order.city}",
        f"Адрес/отделение: {order.delivery_address}",
        "",
        "Товары:",
    ]
    for item in order.items:
        variant = " / ".join(part for part in (item.size, item.color) if part)
        lines.append(
            f"• {item.product_name}"
            f"{f' ({variant})' if variant else ''} — "
            f"{item.quantity} шт. × {item.unit_price_byn:.2f} BYN"
        )
    lines.extend(
        [
            f"Товары: {order.items_total_byn:.2f} BYN",
            (
                f"Доставка: {order.delivery_price_byn:.2f} BYN"
                if order.delivery_price_byn is not None
                else f"Доставка: {order.delivery_price_note or 'по договорённости'}"
            ),
            f"Итого: {order.total_byn:.2f} BYN",
        ]
    )
    if order.comment:
        lines.extend(["", f"Комментарий: {order.comment}"])
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3850].rsplit("\n", 1)[0] + "\n…"
    return text


def _format_customer_status(order: Order, status: str) -> str:
    return (
        f"Обновление по заказу №{str(order.id)[:8]}: "
        f"{STATUS_LABELS[status].lower()}."
    )


async def _event_message(
    session: AsyncSession, event: NotificationOutbox
) -> tuple[str, Optional[InlineKeyboardMarkup], list[int]]:
    try:
        order_id = uuid.UUID(event.payload["order_id"])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(f"В событии {event.id} указан некорректный order_id.") from error

    order = await session.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    if order is None:
        raise ValueError(f"Заказ для события {event.id} не найден.")
    if event.event_type == "new_order":
        user = await session.get(User, order.user_id)
        if user is None:
            raise ValueError(f"Покупатель заказа {order.id} не найден.")
        recipients = sorted(get_settings().privileged_ids)
        if not recipients:
            raise ValueError("Для уведомлений задайте ADMIN_IDS или MANAGER_TELEGRAM_ID.")
        return (
            _format_manager_order(order, user),
            _order_keyboard(order.id, order.status),
            recipients,
        )
    if event.event_type == "order_status":
        user = await session.get(User, order.user_id)
        if user is None:
            raise ValueError(f"Покупатель заказа {order.id} не найден.")
        status = event.payload.get("status")
        if status not in STATUS_LABELS:
            raise ValueError(f"Для события {event.id} указан неизвестный статус.")
        return _format_customer_status(order, status), None, [user.telegram_id]
    raise ValueError(f"Неизвестный тип события outbox: {event.event_type}.")


async def _deliver_event(bot: Bot, event_id: uuid.UUID) -> None:
    async with SessionFactory() as session:
        event = await session.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.id == event_id,
                NotificationOutbox.completed_at.is_(None),
                NotificationOutbox.available_at <= datetime.now(timezone.utc),
            )
            .with_for_update(skip_locked=True)
        )
        if event is None:
            return
        text, keyboard, recipients = await _event_message(session, event)
        delivered_to = set(event.payload.get("delivered_to", []))
        for recipient_id in recipients:
            if recipient_id in delivered_to:
                continue
            try:
                await bot.send_message(
                    chat_id=recipient_id,
                    text=text,
                    reply_markup=keyboard,
                )
            except (TelegramNetworkError, TelegramServerError, TelegramRetryAfter) as error:
                event.attempts += 1
                delay = min(2**event.attempts, MAX_BACKOFF_SECONDS)
                event.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                event.payload = {
                    **event.payload,
                    "delivered_to": sorted(delivered_to),
                }
                event.last_error = f"{type(error).__name__}: {error}"[:2000]
                await session.commit()
                logger.warning(
                    "Временная ошибка доставки события %s; повтор через %s сек.",
                    event.id,
                    delay,
                )
                return
            except TelegramAPIError as error:
                delivered_to.add(recipient_id)
                event.payload = {
                    **event.payload,
                    "delivered_to": sorted(delivered_to),
                }
                event.last_error = f"{type(error).__name__}: {error}"[:2000]
                logger.error(
                    "Telegram отклонил отправку события %s получателю %s: %s",
                    event.id,
                    recipient_id,
                    error,
                )
                continue
            delivered_to.add(recipient_id)
            event.payload = {
                **event.payload,
                "delivered_to": sorted(delivered_to),
            }
        event.completed_at = datetime.now(timezone.utc)
        await session.commit()


async def notification_worker(bot: Bot) -> None:
    """Периодически выбирает ожидающие события, удерживая блокировку на событии."""
    while True:
        try:
            async with SessionFactory() as session:
                event_ids = list(
                    (
                        await session.scalars(
                            select(NotificationOutbox.id)
                            .where(
                                NotificationOutbox.completed_at.is_(None),
                                NotificationOutbox.available_at
                                <= datetime.now(timezone.utc),
                            )
                            .order_by(NotificationOutbox.created_at)
                            .limit(20)
                        )
                    ).all()
                )
            for event_id in event_ids:
                try:
                    await _deliver_event(bot, event_id)
                except Exception:
                    logger.exception("Не удалось обработать событие outbox %s.", event_id)
                    async with SessionFactory.begin() as session:
                        event = await session.scalar(
                            select(NotificationOutbox)
                            .where(NotificationOutbox.id == event_id)
                            .with_for_update()
                        )
                        if event is not None and event.completed_at is None:
                            event.attempts += 1
                            delay = min(2**event.attempts, MAX_BACKOFF_SECONDS)
                            event.available_at = datetime.now(timezone.utc) + timedelta(
                                seconds=delay
                            )
                            event.last_error = "Ошибка обработки события; подробности в журнале."
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка цикла обработки уведомлений.")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
