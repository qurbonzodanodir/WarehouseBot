from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import RoleFilter
from app.bot.keyboards.inline import delivery_confirm_kb, order_action_kb
from app.models.enums import OrderStatus, UserRole
from app.models.user import User
from app.services import order_service

router = Router(name="warehouse")
router.message.filter(RoleFilter(UserRole.WAREHOUSE))
router.callback_query.filter(RoleFilter(UserRole.WAREHOUSE))




@router.message(F.text == "🔔 Активные запросы")
async def active_requests(
    message: Message, session: AsyncSession
) -> None:
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
        from app.services.user_service import get_user_by_telegram_id
        from sqlalchemy import select
        from app.models.user import User as UserModel

        stmt = select(UserModel).where(
            UserModel.store_id == order.store_id,
            UserModel.role == UserRole.SELLER,
            UserModel.is_active.is_(True),
        )
        result = await session.execute(stmt)
        sellers = result.scalars().all()
        for seller in sellers:
            try:
                await bot.send_message(
                    chat_id=seller.telegram_id,
                    text=(
                        f"📬 Курьер выехал!\n"
                        f"Заявка #{order.id}: {order.quantity} шт"
                    ),
                    reply_markup=delivery_confirm_kb(order.id, order.quantity),
                )
            except Exception:
                pass  # seller might have blocked the bot

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




@router.message(F.text == "📦 Остатки склада")
async def warehouse_stock(
    message: Message, user: User, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id)
    if not items:
        await message.answer("Склад пуст.")
        return

    lines = ["📦 <b>Остатки склада:</b>\n"]
    for inv in items:
        lines.append(
            f"• {inv.product.sku} — {inv.product.name}: "
            f"<b>{inv.quantity}</b> шт"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")




@router.message(F.text == "🚚 История отгрузок")
async def shipment_history(
    message: Message, session: AsyncSession
) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.order import Order

    stmt = (
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.status.in_([OrderStatus.DISPATCHED, OrderStatus.DELIVERED]))
        .order_by(Order.created_at.desc())
        .limit(15)
    )
    result = await session.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        await message.answer("Нет отгрузок.")
        return

    lines = ["🚚 <b>Последние отгрузки:</b>\n"]
    for o in orders:
        status_emoji = "🚛" if o.status == OrderStatus.DISPATCHED else "✅"
        lines.append(
            f"{status_emoji} #{o.id} → {o.store.name} | "
            f"{o.product.name} x{o.quantity}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")
