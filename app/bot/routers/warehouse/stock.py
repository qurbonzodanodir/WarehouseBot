from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.user import User
from app.services import order_service

router = Router(name="warehouse.stock")


async def _send_stock_page(
    message_or_callback: Message | CallbackQuery, 
    items: list, 
    page: int
) -> None:
    from app.bot.keyboards.inline import get_page_slice, add_pagination_buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    limit = 20
    
    if not items:
        text = "Склад пуст."
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.edit_text(text)
        return

    start, end = get_page_slice(len(items), page, limit)
    page_items = items[start:end]

    lines = [f"📦 <b>Остатки склада (стр {page + 1}):</b>\n"]
    for inv in page_items:
        lines.append(
            f"• {inv.product.sku} — {inv.product.name}: "
            f"<b>{inv.quantity}</b> шт"
        )
        
    builder = InlineKeyboardBuilder()
    add_pagination_buttons(builder, len(items), page, limit, "stock:page")
    
    markup = builder.as_markup() if len(builder.as_markup().inline_keyboard) > 0 else None
    
    text = "\n".join(lines)
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)


@router.message(F.text == "📦 Остатки")
async def warehouse_stock(
    message: Message, user: User, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id)
    await _send_stock_page(message, items, page=0)


@router.callback_query(F.data.startswith("stock:page:"))
async def warehouse_stock_page_nav(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    items = await order_service.get_store_inventory(session, user.store_id)
    await _send_stock_page(callback, items, page)
    await callback.answer()


@router.message(F.text == "🚚 Отгрузки")
async def shipment_history(
    message: Message, session: AsyncSession
) -> None:
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
