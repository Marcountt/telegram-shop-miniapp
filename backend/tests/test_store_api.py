import unittest
import uuid
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.api.store import (
    MAX_CART_LINES,
    _convert_price,
    _manager_message,
    _product_conditions,
)
from app.api.store_schemas import OrderCreate, StoreSizeOptionOut
from app.db.models import Order as StoreOrder, OrderItem, Product
from app.main import app


class StoreAPITests(unittest.TestCase):
    def test_currency_conversion_uses_byn_to_rub_rate(self) -> None:
        self.assertEqual(_convert_price(Decimal("12.34"), "RUB", Decimal("30")), Decimal("370.20"))
        self.assertEqual(_convert_price(Decimal("12.34"), "BYN", Decimal("30")), Decimal("12.34"))

    def test_section_filter_includes_unisex(self) -> None:
        conditions = _product_conditions(
            search="brand",
            section="women",
            group="clothing",
            category_id=None,
            size=None,
            on_sale=True,
            in_stock=True,
            min_price=Decimal("10"),
            max_price=None,
            currency="RUB",
            rate=Decimal("30"),
        )
        statement = select(Product).where(*conditions)
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("products.section IN", sql)
        self.assertIn("products.name ILIKE", sql)
        self.assertIn("products.brand ILIKE", sql)
        self.assertIn("categories.group_key", sql)
        self.assertIn("product_variants.stock", sql)
        self.assertIn("products.sale_price_rub", sql)

    def test_order_requires_delivery_location(self) -> None:
        fields = {
            "recipient_name": "Покупатель",
            "phone": "+375291234567",
            "delivery_method_id": uuid.uuid4(),
            "city": "Гродно",
        }
        with self.assertRaises(ValidationError):
            OrderCreate(**fields)
        order_request = OrderCreate(**fields, branch="Отделение 3")
        self.assertEqual(order_request.branch, "Отделение 3")

    def test_customer_profile_and_size_filter_routes_are_documented(self) -> None:
        paths = set(app.openapi()["paths"])
        self.assertIn("/api/me", paths)
        self.assertIn("/api/store/sizes", paths)
        size_option = StoreSizeOptionOut(
            id=uuid.uuid4(),
            group_key="clothing",
            value="M",
            sort_order=1,
        )
        self.assertEqual(size_option.value, "M")
        self.assertIn("/api/store/sizes", app.openapi()["paths"])

    def test_manager_message_contains_order_data_and_is_bounded(self) -> None:
        order = StoreOrder(
            id=uuid.uuid4(),
            recipient_name="Покупатель",
            phone="+375291234567",
            delivery_method_name="Европочта",
            city="Гродно",
            delivery_address="Отделение 3",
            comment="Комментарий к заказу " * 20,
            currency="BYN",
            total_byn=Decimal("155.00"),
            items=[
                OrderItem(
                    product_name=f"Очень длинное название товара номер {index}",
                    size="XL",
                    color="Черный",
                    quantity=index + 1,
                    unit_price_byn=Decimal("20"),
                )
                for index in range(MAX_CART_LINES)
            ],
        )
        message = _manager_message(order, Decimal("30"))
        self.assertLessEqual(len(message), 1000)
        self.assertIn("Покупатель", message)
        self.assertIn("+375291234567", message)
        self.assertIn("Европочта", message)
        self.assertIn("x8", message)


if __name__ == "__main__":
    unittest.main()
