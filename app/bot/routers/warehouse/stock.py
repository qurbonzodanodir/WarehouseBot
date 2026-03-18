from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from typing import Any
from app.models.enums import OrderStatus
from app.models.order import Order
from app.models.user import User
from app.services import OrderService

router = Router(name="warehouse.stock")


async def _send_stock_page(
    message_or_callback: Message | CallbackQuery, 
    items: list, 
    page: int,
    _: Any,
) -> None:
    from app.bot.keyboards.inline import get_page_slice, add_pagination_buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    limit = 20
    
    if not items:
        text = _("stock_empty")
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.edit_text(text)
        return

    start, end = get_page_slice(len(items), page, limit)
    page_items = items[start:end]

    lines = [_(
        "stock_title",
        page=page + 1
    )]
    for inv in page_items:
        lines.append(
            f"• {inv.product.sku}: "
            f"<b>{inv.quantity}</b> " + _("unit_pcs")
        )
        
    builder = InlineKeyboardBuilder()
    add_pagination_buttons(builder, len(items), page, limit, "stock:page", _=_)
    
    markup = builder.as_markup() if len(builder.as_markup().inline_keyboard) > 0 else None
    
    text = "\n".join(lines)
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)


@router.message(F.text.in_({"📦 Остатки", "📦 Боқимонда"}))
async def warehouse_stock(
    message: Message, user: User, session: AsyncSession, _: Any
) -> None:
    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    
    if not warehouse_id:
        await message.answer(_("warehouse_not_found"))
        return

    order_svc = OrderService(session)
    items = await order_svc.get_store_inventory(warehouse_id)
    await _send_stock_page(message, items, page=0, _=_)


@router.callback_query(F.data.startswith("stock:page:"))
async def warehouse_stock_page_nav(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    
    if not warehouse_id:
        await callback.answer(_("warehouse_not_found"), show_alert=True)
        return

    order_svc = OrderService(session)
    items = await order_svc.get_store_inventory(warehouse_id)
    await _send_stock_page(callback, items, page, _=_)
    await callback.answer()


@router.message(F.text.in_({"🚚 Отгрузки", "🚚 Ирсолҳо"}))
async def shipment_history(
    message: Message, session: AsyncSession, _: Any
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
        await message.answer(_("shipment_history_empty"))
        return

    lines = [_(
        "shipment_history_title"
    )]
    for o in orders:
        status_emoji = "🚛" if o.status == OrderStatus.DISPATCHED else "✅"
        lines.append(
            f"{status_emoji} #{o.id} → {o.store.name} | "
            f"{o.product.sku} x{o.quantity}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")
