from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import delivery_confirm_kb, order_action_kb
from app.models.user import User
from app.services import notification_service, order_service, transaction_service

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

@router.callback_query(F.data.startswith("order:approve_return:"))
async def approve_return(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        from app.models.order import Order
        order = await session.get(Order, order_id)
        if not order:
            await callback.message.edit_text("❌ Заявка не найдена.")
            return

        store_id = order.store_id
        
        txn = await transaction_service.approve_return(
            session,
            warehouse_store_id=user.store_id,
            warehouse_user_id=user.id,
            order_id=order_id,
        )
        await session.commit()
        await callback.message.edit_text(
            f"✅ Возврат по заявке #{order_id} принят!\n"
            f"Товар зачислен на Главный Склад, долг магазина уменьшен на {txn.amount} сом."
        )

        from app.bot.bot import bot
        await notification_service.notify_sellers(
            bot=bot,
            session=session,
            store_id=store_id,
            text=f"✅ <b>Склад принял ваш возврат (Заявка #{order_id})!</b>\nВаш долг был уменьшен на {txn.amount} сом.",
            reply_markup=None,
        )

    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка принятия возврата: {e}")
    except Exception as e:
        await callback.message.edit_text("❌ Произошла ошибка. Обратитесь к администратору.")
        print(f"Error in approve_return: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:reject_return:"))
async def reject_return_request(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        from app.models.order import Order
        order = await session.get(Order, order_id)
        if not order:
            await callback.message.edit_text("❌ Заявка не найдена.")
            return

        store_id = order.store_id
        
        await transaction_service.reject_return(
            session,
            order_id=order_id,
        )
        await session.commit()
        await callback.message.edit_text(
            f"❌ Вы отклонили возврат по заявке #{order_id}.\nТовар возвращен на витрину магазина."
        )

        from app.bot.bot import bot
        await notification_service.notify_sellers(
            bot=bot,
            session=session,
            store_id=store_id,
            text=f"❌ <b>Склад ОТКЛОНИЛ ваш возврат (Заявка #{order_id})!</b>\nТовар возвращен на вашу витрину, долг не списан.",
            reply_markup=None,
        )

    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    except Exception as e:
        await callback.message.edit_text("❌ Произошла ошибка. Обратитесь к администратору.")
        print(f"Error in reject_return_request: {e}")
    finally:
        await callback.answer()
