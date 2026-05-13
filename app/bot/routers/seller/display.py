from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Any
from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.user import User

router = Router(name="seller.display")


def _brand(order: Order) -> str:
    value = (getattr(order.product, "brand", "") or "").strip()
    if not value or value.upper() == "UNKNOWN":
        return "-"
    return value


@router.callback_query(F.data.startswith("display:receive:"))
async def seller_receive_display(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    order = await session.get(
        Order, order_id, options=[selectinload(Order.product)]
    )
    if not order or order.store_id != user.store_id or order.status != OrderStatus.DISPLAY_DISPATCHED:
        await callback.answer(_("display_not_found"), show_alert=True)
        return

    from app.services import TransactionService
    # Credit store inventory
    txn_svc = TransactionService(session)
    await txn_svc.receive_display_items(order_id)
    await session.commit()

    await callback.message.edit_text(
        _("display_received_seller", sku=order.product.sku, brand=_brand(order), qty=order.quantity),
        parse_mode="HTML"
    )

    from app.services import NotificationService
    # Notify warehouse
    notif_svc = NotificationService(callback.bot, session)
    await notif_svc.notify_warehouse(
        text=lambda _t: _t("display_received_wh", store=user.store.name if user.store else _t("unknown"), sku=order.product.sku, brand=_brand(order), qty=order.quantity)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("display:reject:"))
async def seller_reject_display(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    order = await session.get(
        Order, order_id, options=[selectinload(Order.product)]
    )
    if not order or order.store_id != user.store_id or order.status != OrderStatus.DISPLAY_DISPATCHED:
        await callback.answer(_("display_not_found"), show_alert=True)
        return

    from app.services import TransactionService
    from app.services import StoreService

    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        await callback.answer(_("warehouse_not_found"), show_alert=True)
        return

    txn_svc = TransactionService(session)
    await txn_svc.reject_display_items(
        order_id=order_id,
        warehouse_store_id=warehouse_id,
        user_id=user.id,
    )
    await session.commit()

    await callback.message.edit_text(
        _("display_rejected_seller", sku=order.product.sku, brand=_brand(order), qty=order.quantity),
        parse_mode="HTML"
    )

    from app.services import NotificationService
    # Notify warehouse
    notif_svc = NotificationService(callback.bot, session)
    await notif_svc.notify_warehouse(
        text=lambda _t: _t("display_rejected_wh", store=user.store.name if user.store else _t("unknown"), sku=order.product.sku, brand=_brand(order), qty=order.quantity)
    )
    await callback.answer()
