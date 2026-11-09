import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.telegram_auth import validate_init_data


class BackendSettingsTests(unittest.TestCase):
    def test_admin_ids_are_loaded_from_requested_environment_variable(self) -> None:
        with patch.dict(os.environ, {"ADMIN_IDS": "123456789, 987654321"}):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.admin_ids, {123456789, 987654321})


class TelegramInitDataTests(unittest.TestCase):
    """Короткие проверки проверки подписи Telegram Mini App."""

    bot_token = "test-bot-token"
    auth_date = 1_800_000_000

    def make_init_data(self) -> str:
        fields = {
            "auth_date": str(self.auth_date),
            "user": json.dumps(
                {
                    "id": 123456,
                    "first_name": "Тест",
                    "username": "test_user",
                    "photo_url": "https://t.me/i/userpic/320/test.jpg",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        data_check_string = "\n".join(
            "{}={}".format(key, value) for key, value in sorted(fields.items())
        )
        secret_key = hmac.new(
            b"WebAppData",
            self.bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        fields["hash"] = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return urlencode(fields)

    def test_accepts_valid_signature_and_rejects_tampering_or_expiry(self) -> None:
        init_data = self.make_init_data()

        parsed = validate_init_data(
            init_data,
            self.bot_token,
            max_age_seconds=60,
            now=self.auth_date + 30,
        )
        self.assertEqual(parsed["user"]["id"], 123456)
        self.assertEqual(parsed["user"]["username"], "test_user")
        self.assertEqual(
            parsed["user"]["photo_url"],
            "https://t.me/i/userpic/320/test.jpg",
        )

        tampered_data = init_data.replace("%D0%A2%D0%B5%D1%81%D1%82", "Hacker")
        with self.assertRaisesRegex(ValueError, "Подпись"):
            validate_init_data(
                tampered_data,
                self.bot_token,
                max_age_seconds=60,
                now=self.auth_date + 30,
            )

        with self.assertRaisesRegex(ValueError, "истёк"):
            validate_init_data(
                init_data,
                self.bot_token,
                max_age_seconds=60,
                now=self.auth_date + 61,
            )


if __name__ == "__main__":
    unittest.main()
