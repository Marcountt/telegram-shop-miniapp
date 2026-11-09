import asyncio
import unittest
from collections import Counter
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import Select
from sqlalchemy.dialects import postgresql

from app.db.models import Product
from app.db.seed import (
    CATEGORIES,
    DEMO_PRODUCTS,
    DELIVERY_METHODS,
    HOW_TO_ORDER_STEPS,
    SIZE_OPTIONS,
    STORE_SETTINGS,
    placeholder_image_url,
    seed_database,
)


PRODUCT_SLUGS = {product["slug"] for product in DEMO_PRODUCTS}


class _Result:
    def __init__(self, slugs: set[str]) -> None:
        self.slugs = slugs

    def all(self) -> list[tuple[str, object]]:
        return [(slug, uuid4()) for slug in self.slugs]


class _Session:
    def __init__(self) -> None:
        self.statements = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    async def execute(self, statement):
        self.statements.append(statement)
        if isinstance(statement, Select):
            selected = statement.column_descriptions[0]["expr"]
            slugs = (
                PRODUCT_SLUGS
                if getattr(selected, "table", None).name == "products"
                else {category["slug"] for category in CATEGORIES}
            )
            return _Result(slugs)
        return None


class StoreSeedTests(unittest.TestCase):
    def test_store_defaults_match_requested_values(self) -> None:
        self.assertEqual(STORE_SETTINGS["manager_username"], "your_manager")
        self.assertEqual(STORE_SETTINGS["reviews_url"], "https://t.me/your_reviews_channel")
        self.assertEqual(STORE_SETTINGS["byn_to_rub_rate"], 30)
        self.assertEqual(STORE_SETTINGS["store_name"], "BRAND GRODNO")
        self.assertEqual(len(HOW_TO_ORDER_STEPS), 4)

    def test_delivery_methods_have_requested_prices_and_are_active(self) -> None:
        methods = {method["code"]: method for method in DELIVERY_METHODS}
        self.assertEqual(methods["belpochta"]["price_byn"], 5)
        self.assertEqual(methods["europochta"]["price_byn"], 6)
        self.assertEqual(methods["cdek"]["price_note"], "по договорённости")
        self.assertEqual(methods["courier"]["price_note"], "по договорённости")
        self.assertTrue(all(method["is_active"] for method in methods.values()))

    def test_demo_catalog_has_eight_products_and_placeholder_images(self) -> None:
        counts = Counter(product["category_slug"] for product in DEMO_PRODUCTS)
        self.assertEqual(len(DEMO_PRODUCTS), 8)
        self.assertEqual(counts, {"odezhda": 4, "aksessuary": 2, "obuv": 2})
        self.assertTrue(
            all(
                placeholder_image_url(product["image_text"]).startswith("https://placehold.co/")
                for product in DEMO_PRODUCTS
            )
        )
        self.assertEqual(len(CATEGORIES), 3)
        groups = {category["slug"]: category["group_key"] for category in CATEGORIES}
        self.assertEqual(groups["odezhda"], "clothing")
        self.assertEqual(groups["aksessuary"], "clothing")
        self.assertEqual(groups["obuv"], "shoes")

    def test_product_sold_at_is_nullable(self) -> None:
        self.assertTrue(Product.__table__.c.sold_at.nullable)

    def test_seed_contains_size_options_for_clothing_and_shoes(self) -> None:
        groups = {option["group_key"] for option in SIZE_OPTIONS}
        self.assertEqual(groups, {"clothing", "shoes"})
        self.assertIn("M", {option["value"] for option in SIZE_OPTIONS})
        self.assertIn("42", {option["value"] for option in SIZE_OPTIONS})

    def test_seed_inserts_explicit_ids_for_bulk_rows(self) -> None:
        session = _Session()
        asyncio.run(seed_database(session))

        inserts = {
            statement.table.name: statement
            for statement in session.statements
            if getattr(statement, "is_insert", False)
        }
        for table_name in ("categories", "products", "product_variants", "delivery_methods"):
            parameters = inserts[table_name].compile(
                dialect=postgresql.dialect()
            ).params
            ids = [value for key, value in parameters.items() if key.startswith("id")]
            self.assertTrue(ids)
            self.assertTrue(all(value is not None for value in ids))


if __name__ == "__main__":
    unittest.main()
