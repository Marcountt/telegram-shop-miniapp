import io
import unittest
import uuid
from decimal import Decimal

from PIL import Image
from pydantic import ValidationError

from app.api.admin import (
    _apply_product_payload,
    _image_response,
    _normalize_image,
    router,
)
from app.api.admin_schemas import AdminDashboardOut, AdminProductWrite
from app.api.dependencies import require_admin
from app.db.models import Product
from app.api.store import _display_product_price
from app.main import app


class AdminSchemaTests(unittest.TestCase):
    def test_manual_rub_price_and_old_price_are_validated(self):
        payload = AdminProductWrite(
            title="Худи",
            category_id=uuid.uuid4(),
            price_byn="100",
            price_rub="3000",
            rub_price_mode="manual",
            old_price_byn="120",
            old_price_rub="3500",
            sizes=[{"size": "M"}, {"size": "L", "quantity": 0}],
            is_new=True,
        )
        self.assertEqual(payload.sizes[0].quantity, 1)
        self.assertTrue(payload.is_new)

        with self.assertRaises(ValidationError):
            AdminProductWrite(
                title="Худи",
                category_id=uuid.uuid4(),
                price_byn="100",
                rub_price_mode="manual",
            )

    def test_discount_prices_are_stored_as_current_and_original_values(self):
        product = Product(
            slug="product-test",
            photos=[],
            sizes=[],
            colors=[],
            is_active=True,
        )
        payload = AdminProductWrite(
            title="Худи",
            category_id=uuid.uuid4(),
            price_byn="100",
            price_rub="3000",
            rub_price_mode="manual",
            old_price_byn="120",
            old_price_rub="3500",
        )

        _apply_product_payload(product, payload, Decimal("30"))

        self.assertEqual(product.price_byn, Decimal("120"))
        self.assertEqual(product.sale_price_byn, Decimal("100"))
        self.assertEqual(product.price_rub, Decimal("3500"))
        self.assertEqual(product.sale_price_rub, Decimal("3000"))

    def test_manual_rub_price_is_used_in_public_catalog(self):
        product = Product(
            name="Худи",
            price_byn=Decimal("120"),
            sale_price_byn=Decimal("100"),
            price_rub=Decimal("3500"),
            sale_price_rub=Decimal("3000"),
        )

        self.assertEqual(
            _display_product_price(product, "RUB", Decimal("30")),
            Decimal("3000.00"),
        )
        self.assertEqual(
            _display_product_price(
                product, "RUB", Decimal("30"), original=True
            ),
            Decimal("3500.00"),
        )

    def test_admin_routes_all_require_admin_dependency(self):
        self.assertTrue(router.dependencies)
        self.assertTrue(
            all(item.dependency is require_admin for item in router.dependencies)
        )
        paths = set(app.openapi()["paths"])
        self.assertIn("/api/admin/products", paths)
        self.assertIn("/api/admin/products/{product_id}", paths)
        self.assertIn("/api/admin/dashboard", paths)
        self.assertIn("/api/admin/products/{product_id}/sold", paths)
        self.assertIn("/api/admin/orders/{order_id}/status", paths)
        self.assertIn("/api/admin/settings/delivery-methods/{method_id}", paths)

    def test_dashboard_schema_contains_requested_owner_metrics(self):
        dashboard = AdminDashboardOut(
            pending_orders=2,
            today_orders=4,
            today_revenue_byn="120.50",
            week_orders=12,
            week_revenue_byn="900.00",
            one_size_left=[],
        )
        self.assertEqual(dashboard.pending_orders, 2)
        self.assertEqual(dashboard.week_revenue_byn, Decimal("900.00"))


class AdminImageTests(unittest.TestCase):
    def test_legacy_image_gets_stable_id_and_can_be_selected_as_cover(self):
        image = {"url": "https://placehold.co/item.png", "alt": "Товар"}

        first = _image_response(image, 0)
        next_read = _image_response(image, 0)

        self.assertEqual(first.id, next_read.id)
        self.assertEqual(first.thumbnail_url, image["url"])
        self.assertTrue(first.is_cover)

    def test_image_is_converted_resized_and_thumbnailed_as_webp(self):
        source = Image.new("RGB", (2000, 1000), color=(200, 30, 40))
        raw = io.BytesIO()
        source.save(raw, format="PNG")

        full, thumbnail = _normalize_image(raw.getvalue())

        with Image.open(io.BytesIO(full)) as converted:
            self.assertEqual(converted.format, "WEBP")
            self.assertEqual(converted.size, (1600, 800))
        with Image.open(io.BytesIO(thumbnail)) as converted_thumb:
            self.assertEqual(converted_thumb.format, "WEBP")
            self.assertLessEqual(max(converted_thumb.size), 500)

    def test_non_image_data_is_rejected(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as error:
            _normalize_image(b"not an image")
        self.assertEqual(error.exception.status_code, 415)


if __name__ == "__main__":
    unittest.main()
