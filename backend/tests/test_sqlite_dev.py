import asyncio
import unittest
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.catalog import _apply_open_now_filter
from app.db.base import Base
from app.db.models import Category, Place, PlaceStatus, Product, StoreSettings
from app.db.seed import seed_database


class SQLiteDevelopmentTests(unittest.TestCase):
    def test_metadata_and_demo_seed_run_on_sqlite(self) -> None:
        async def run() -> tuple[int, int, str, int]:
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            try:
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with sessions.begin() as session:
                    await seed_database(session)
                async with sessions() as session:
                    product_count = await session.scalar(
                        select(func.count()).select_from(Product)
                    )
                    category_count = await session.scalar(
                        select(func.count()).select_from(Category)
                    )
                    store_name = await session.scalar(
                        select(StoreSettings.store_name).where(StoreSettings.id == 1)
                    )
                    open_place = Place(
                        name="Открыто",
                        status=PlaceStatus.PUBLISHED,
                        working_hours={"monday": [{"open": "09:00", "close": "18:00"}]},
                    )
                    closed_place = Place(
                        name="Закрыто",
                        status=PlaceStatus.PUBLISHED,
                        working_hours={"monday": [{"open": "13:00", "close": "18:00"}]},
                    )
                    session.add_all([open_place, closed_place])
                    await session.flush()
                    open_places = await session.scalars(
                        _apply_open_now_filter(
                            select(Place),
                            datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
                            engine.dialect.name,
                        )
                    )
                    return (
                        int(product_count or 0),
                        int(category_count or 0),
                        store_name,
                        len(open_places.all()),
                    )
            finally:
                await engine.dispose()

        products, categories, store_name, open_places = asyncio.run(run())
        self.assertEqual(products, 8)
        self.assertEqual(categories, 3)
        self.assertEqual(store_name, "DEMO STORE")
        self.assertEqual(open_places, 1)


if __name__ == "__main__":
    unittest.main()
