"""Initialize a disposable local SQLite database for development."""
import asyncio

from app.core.config import get_settings
from app.db.base import Base
from app.db.models import (  # noqa: F401
    CartItem,
    Category,
    DeliveryMethod,
    Favorite,
    NotificationOutbox,
    Order,
    OrderItem,
    Place,
    Product,
    ProductFavorite,
    ProductVariant,
    Review,
    SizeOption,
    StoreSettings,
    Submission,
    User,
)
from app.db.seed import seed_database
from app.db.session import SessionFactory, engine


async def initialize_database() -> None:
    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            "The local initializer only supports SQLite. Use Alembic migrations "
            "for PostgreSQL."
        )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionFactory.begin() as session:
        await seed_database(session)


async def main() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite+aiosqlite:"):
        raise RuntimeError(
            "Set DATABASE_URL=sqlite+aiosqlite:///./local-catalog.db before "
            "running the local initializer."
        )
    await initialize_database()
    await engine.dispose()
    print("SQLite database initialized and seeded.")


if __name__ == "__main__":
    asyncio.run(main())
