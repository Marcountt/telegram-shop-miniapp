"""Проверка переходов статуса заказа и складских остатков."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NotificationOutbox, Order, OrderItem, ProductVariant


STATUS_LABELS = {
    "pending": "Ожидает подтверждения",
    "processing": "Подтверждён",
    "shipped": "Отправлен",
    "completed": "Доставлен",
    "cancelled": "Отменён",
}

ACTION_TARGETS = {
    "confirm": ("pending", "processing"),
    "shipped": ("processing", "shipped"),
    "delivered": ("shipped", "completed"),
    "cancel": (("pending", "processing"), "cancelled"),
}


class OrderActionError(ValueError):
    """Недопустимое или невыполнимое действие над заказом."""


async def change_order_status(
    session: AsyncSession,
    order_id: uuid.UUID,
    action: str,
) -> Order:
    """Атомарно меняет статус, склад и ставит уведомление покупателю в очередь."""
    if action not in ACTION_TARGETS:
        raise OrderActionError("Неизвестное действие.")

    order = await session.scalar(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    if order is None:
        raise OrderActionError("Заказ не найден.")

    allowed_status, target_status = ACTION_TARGETS[action]
    allowed_statuses = (
        set(allowed_status)
        if isinstance(allowed_status, tuple)
        else {allowed_status}
    )
    if order.status not in allowed_statuses:
        raise OrderActionError(
            f"Заказ уже имеет статус «{STATUS_LABELS.get(order.status, order.status)}»."
        )

    items = list(
        (
            await session.scalars(
                select(OrderItem)
                .where(OrderItem.order_id == order.id)
                .order_by(OrderItem.variant_id, OrderItem.id)
            )
        ).all()
    )
    variant_ids = sorted(
        {item.variant_id for item in items if item.variant_id is not None},
        key=str,
    )
    variants = {}
    if variant_ids:
        variants = {
            variant.id: variant
            for variant in (
                await session.scalars(
                    select(ProductVariant)
                    .where(ProductVariant.id.in_(variant_ids))
                    .order_by(ProductVariant.id)
                    .with_for_update()
                )
            ).all()
        }

    if action == "confirm":
        if not items:
            raise OrderActionError("Нельзя подтвердить заказ без товаров.")
        for item in items:
            variant = variants.get(item.variant_id)
            if variant is None:
                raise OrderActionError(
                    f"Вариант товара «{item.product_name}» больше недоступен."
                )
            if variant.stock < item.quantity:
                raise OrderActionError(
                    f"Недостаточно товара «{item.product_name}», размер {item.size}. "
                    f"Доступно: {variant.stock}."
                )
        for item in items:
            variants[item.variant_id].stock -= item.quantity
    elif action == "cancel" and order.status == "processing":
        for item in items:
            variant = variants.get(item.variant_id)
            if variant is not None:
                variant.stock += item.quantity

    order.status = target_status
    session.add(
        NotificationOutbox(
            event_type="order_status",
            payload={
                "order_id": str(order.id),
                "status": target_status,
                "delivered_to": [],
            },
        )
    )
    if action == "confirm":
        order.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return order
