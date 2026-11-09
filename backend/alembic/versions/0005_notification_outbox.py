"""Добавить очередь уведомлений Telegram.

Идентификатор ревизии: 0005_notification_outbox
Предыдущая ревизия: 0004_store_api
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_notification_outbox"
down_revision: Union[str, None] = "0004_store_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name=op.f("ck_notification_outbox_attempts_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_outbox")),
    )
    op.create_index(
        "ix_notification_outbox_pending",
        "notification_outbox",
        ["completed_at", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_pending", table_name="notification_outbox")
    op.drop_table("notification_outbox")
