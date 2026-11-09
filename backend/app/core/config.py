from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Настройки приложения из окружения и корневого файла .env."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Local Catalog API"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+asyncpg://local_catalog:local_catalog@localhost:5432/local_catalog"
    )
    bot_token: str = ""
    admin_telegram_ids: str = Field(
        default="",
        validation_alias=AliasChoices("ADMIN_IDS", "ADMIN_TELEGRAM_IDS"),
    )
    manager_telegram_id: str = ""
    mini_app_url: str = ""
    cors_origins: str = "http://localhost:5173"
    init_data_max_age_seconds: int = 86400
    city_timezone: str = "Europe/Minsk"
    uploads_dir: str = "uploads"

    @property
    def admin_ids(self) -> set[int]:
        """Разбирает список администраторов из CSV-переменной окружения."""
        try:
            return {
                int(value.strip())
                for value in self.admin_telegram_ids.split(",")
                if value.strip()
            }
        except ValueError as error:
            raise ValueError(
                "ADMIN_IDS должен содержать Telegram ID через запятую."
            ) from error

    @property
    def manager_id(self) -> Optional[int]:
        """Возвращает Telegram ID менеджера, если он задан."""
        value = self.manager_telegram_id.strip()
        if not value:
            return None
        try:
            manager_id = int(value)
        except ValueError as error:
            raise ValueError("MANAGER_TELEGRAM_ID должен быть числовым Telegram ID.") from error
        if manager_id <= 0:
            raise ValueError("MANAGER_TELEGRAM_ID должен быть положительным числом.")
        return manager_id

    @property
    def privileged_ids(self) -> set[int]:
        """Telegram ID менеджера и администраторов с правом управления заказами."""
        return self.admin_ids | ({self.manager_id} if self.manager_id is not None else set())

    @property
    def allowed_origins(self) -> list[str]:
        """Возвращает непустые адреса CORS из списка через запятую."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def uploads_path(self) -> Path:
        """Возвращает абсолютный путь к каталогу пользовательских изображений."""
        path = Path(self.uploads_dir).expanduser()
        return path if path.is_absolute() else ROOT_DIR / path


@lru_cache
def get_settings() -> Settings:
    """Возвращает единый экземпляр настроек процесса."""
    return Settings()
