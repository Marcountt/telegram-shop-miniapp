import hashlib
import hmac
import json
import time
from typing import Any, Optional
from urllib.parse import parse_qsl


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int,
    now: Optional[int] = None,
) -> dict[str, Any]:
    """Проверяет подпись Telegram Mini App initData и срок её действия."""
    if not init_data or len(init_data) > 4096:
        raise ValueError("Некорректная длина initData.")
    if not bot_token:
        raise ValueError("Не задан токен Telegram-бота.")
    if max_age_seconds <= 0:
        raise ValueError("Срок действия initData должен быть положительным.")

    try:
        pairs = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=100,
        )
    except ValueError as error:
        raise ValueError("Некорректный формат initData.") from error

    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError("initData содержит повторяющиеся поля.")
        fields[key] = value

    received_hash = fields.pop("hash", "")
    if len(received_hash) != 64 or any(
        character not in "0123456789abcdef" for character in received_hash
    ):
        raise ValueError("В initData отсутствует корректная подпись.")

    data_check_string = "\n".join(
        "{}={}".format(key, value) for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Подпись initData не прошла проверку.")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError) as error:
        raise ValueError("В initData отсутствует корректный auth_date.") from error

    current_time = int(time.time()) if now is None else now
    age = current_time - auth_date
    if age < -30 or age > max_age_seconds:
        raise ValueError("Срок действия initData истёк или дата находится в будущем.")

    try:
        user = json.loads(fields["user"])
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError("В initData отсутствуют корректные данные пользователя.") from error

    if (
        not isinstance(user, dict)
        or isinstance(user.get("id"), bool)
        or not isinstance(user.get("id"), int)
        or user["id"] <= 0
    ):
        raise ValueError("Telegram ID пользователя в initData некорректен.")

    fields["user"] = user
    fields["auth_date"] = str(auth_date)
    return fields
