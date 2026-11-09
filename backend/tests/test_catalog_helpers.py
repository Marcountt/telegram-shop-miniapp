import unittest
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite

from app.api.catalog import (
    _apply_open_now_filter,
    _decode_cursor,
    _encode_cursor,
    _filter_key,
)
from app.api.schemas import WorkingInterval
from app.db.models import Place


class CatalogHelperTests(unittest.TestCase):
    def test_cursor_round_trip_and_filter_binding(self) -> None:
        filters = _filter_key("кофе", None, "центр", 4.0, False)
        place_id = uuid.uuid4()
        cursor = _encode_cursor("rating", "4.25", place_id, filters)

        position, decoded_place_id = _decode_cursor(cursor, "rating", filters)
        self.assertEqual(str(position), "4.25")
        self.assertEqual(decoded_place_id, place_id)

        with self.assertRaises(HTTPException):
            _decode_cursor(
                cursor,
                "rating",
                _filter_key("кофе", None, "другой район", 4.0, False),
            )

    def test_open_now_filter_uses_local_weekday_and_time(self) -> None:
        query = _apply_open_now_filter(
            select(Place),
            datetime(2026, 11, 2, 12, 0, tzinfo=ZoneInfo("Europe/Minsk")),
        )
        sql = str(query.compile(dialect=postgresql.dialect()))
        self.assertIn("jsonb_array_elements", sql)
        self.assertIn("jsonb_extract_path_text", sql)

    def test_open_now_filter_compiles_for_sqlite_json1(self) -> None:
        query = _apply_open_now_filter(
            select(Place),
            datetime(2026, 11, 2, 12, 0, tzinfo=ZoneInfo("Europe/Minsk")),
            "sqlite",
        )
        sql = str(query.compile(dialect=sqlite.dialect()))
        self.assertIn("json_each", sql)
        self.assertIn("json_extract", sql)
        self.assertNotIn("jsonb_array_elements", sql)

    def test_working_interval_requires_close_after_open(self) -> None:
        interval = WorkingInterval(open="09:00", close="18:00")
        self.assertEqual(interval.open.strftime("%H:%M"), "09:00")
        with self.assertRaises(ValueError):
            WorkingInterval(open="18:00", close="09:00")


if __name__ == "__main__":
    unittest.main()
