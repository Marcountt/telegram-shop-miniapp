import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot.notifications import _event_message
from app.bot.orders import OrderActionError, change_order_status


def _result(rows):
    return SimpleNamespace(all=lambda: rows)


@pytest.mark.asyncio
async def test_confirm_decreases_stock_and_queues_customer_notification():
    order_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    order = SimpleNamespace(id=order_id, status="pending", updated_at=None)
    item = SimpleNamespace(
        variant_id=variant_id,
        quantity=2,
        product_name="Худи",
        size="M",
    )
    variant = SimpleNamespace(id=variant_id, stock=5)
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=order),
        scalars=AsyncMock(side_effect=[_result([item]), _result([variant])]),
        add=Mock(),
        flush=AsyncMock(),
    )

    changed = await change_order_status(session, order_id, "confirm")

    assert changed.status == "processing"
    assert variant.stock == 3
    session.add.assert_called_once()
    assert session.add.call_args.args[0].event_type == "order_status"


@pytest.mark.asyncio
async def test_confirm_rejects_insufficient_stock_without_changing_status():
    order_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    order = SimpleNamespace(id=order_id, status="pending", updated_at=None)
    item = SimpleNamespace(
        variant_id=variant_id,
        quantity=3,
        product_name="Худи",
        size="M",
    )
    variant = SimpleNamespace(id=variant_id, stock=2)
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=order),
        scalars=AsyncMock(side_effect=[_result([item]), _result([variant])]),
        add=Mock(),
        flush=AsyncMock(),
    )

    with pytest.raises(OrderActionError, match="Недостаточно товара"):
        await change_order_status(session, order_id, "confirm")

    assert order.status == "pending"
    assert variant.stock == 2
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_cancelling_confirmed_order_restores_stock():
    order_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    order = SimpleNamespace(id=order_id, status="processing", updated_at=None)
    item = SimpleNamespace(
        variant_id=variant_id,
        quantity=2,
        product_name="Худи",
        size="M",
    )
    variant = SimpleNamespace(id=variant_id, stock=3)
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=order),
        scalars=AsyncMock(side_effect=[_result([item]), _result([variant])]),
        add=Mock(),
        flush=AsyncMock(),
    )

    changed = await change_order_status(session, order_id, "cancel")

    assert changed.status == "cancelled"
    assert variant.stock == 5
    assert session.add.call_args.args[0].event_type == "order_status"


@pytest.mark.asyncio
async def test_customer_notification_uses_status_recorded_in_outbox():
    order_id = uuid.uuid4()
    user_id = uuid.uuid4()
    order = SimpleNamespace(id=order_id, user_id=user_id, status="shipped")
    user = SimpleNamespace(telegram_id=123456)
    event = SimpleNamespace(
        id=uuid.uuid4(),
        event_type="order_status",
        payload={"order_id": str(order_id), "status": "processing"},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=order),
        get=AsyncMock(return_value=user),
    )

    text, keyboard, recipients = await _event_message(session, event)

    assert "подтверждён" in text
    assert keyboard is None
    assert recipients == [123456]
