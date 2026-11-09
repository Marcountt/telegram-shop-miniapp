"""Сохранить фотографию Telegram-профиля пользователя.

Идентификатор ревизии: 0003_user_photo_url
Предыдущая ревизия: 0002_store_products_and_settings
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_user_photo_url"
down_revision: Union[str, None] = "0002_store_products_and_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "photo_url")
