from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


engine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,
)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(connection, _) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Создаёт сессию БД на время обработки запроса."""
    async with SessionFactory() as session:
        yield session
