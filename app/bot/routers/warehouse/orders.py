from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import delivery_confirm_kb, order_action_kb
from app.models.user import User
from app.services import notification_service, order_service

router = Router(name="warehouse.orders")


@router.message(F.text == "🔔 Запросы")
async def active_requests(message: Message, session: AsyncSession) -> None:
    orders = await order_service.get_pending_orders(session)
    if not orders:
        await message.answer("Нет активных запросов. 🎉")
        return

    for order in orders:
        text = (
            f"📋 <b>Заявка #{order.id}</b>\n"
            f"Магазин: {order.store.name}\n"
            f"Товар: {order.product.sku} — {order.product.name}\n"
            f"Кол-во: {order.quantity} шт"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=order_action_kb(order.id),
        )


@router.callback_query(F.data.startswith("order:dispatch:"))
async def dispatch_order(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order = await order_service.dispatch_order(
            session, order_id, warehouse_store_id=user.store_id
        )
        await session.commit()
        await callback.message.edit_text(
            f"🚚 Заявка #{order.id} — курьер отправлен!\n"
            f"Товар: {order.quantity} шт (статус: В пути)"
        )

        from app.bot.bot import bot

        await notification_service.notify_sellers(
            bot=bot,
            session=session,
            store_id=order.store_id,
            text=(
                f"📬 Курьер выехал!\n"
                f"Заявка #{order.id}: {order.quantity} шт"
            ),
            reply_markup=delivery_confirm_kb(order.id, order.quantity),
        )

    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data.startswith("order:reject:"))
async def reject_order(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order = await order_service.reject_order(session, order_id)
        await session.commit()
        await callback.message.edit_text(
            f"❌ Заявка #{order.id} отклонена."
        )
    except ValueError as e:
        await callback.message.edit_text(f"Ошибка: {e}")
    await callback.answer()
