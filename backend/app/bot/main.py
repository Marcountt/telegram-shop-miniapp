"""Точка запуска отдельного процесса Telegram-бота."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.bot.handlers import router
from app.bot.notifications import notification_worker
from app.core.config import get_settings
from app.db.session import engine


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("Укажите BOT_TOKEN в .env.")
    if not settings.mini_app_url.startswith("https://"):
        raise RuntimeError("MINI_APP_URL должен быть публичным HTTPS-адресом Mini App.")
    if not settings.admin_ids:
        raise RuntimeError("Задайте хотя бы один Telegram ID в ADMIN_IDS.")
    if settings.manager_id is None:
        raise RuntimeError("Задайте числовой MANAGER_TELEGRAM_ID в .env.")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(),
    )
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Открыть каталог",
            web_app=WebAppInfo(url=settings.mini_app_url),
        )
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    worker = asyncio.create_task(notification_worker(bot), name="telegram-outbox-worker")
    try:
        await dispatcher.start_polling(bot)
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
