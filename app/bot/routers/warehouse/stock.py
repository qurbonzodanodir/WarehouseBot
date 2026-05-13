from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from app.models.user import User
from app.services import OrderService

router = Router(name="warehouse.stock")


def _clean_brand(brand: str | None) -> str:
    value = (brand or "").strip()
    if not value or value.upper() == "UNKNOWN":
        return "-"
    return value[:12]


def _format_inventory_table(items: list, _: Any) -> str:
    lines = [
        f"{_('stock_col_sku'):<9} {_('stock_col_brand'):<12} {_('stock_col_qty'):>3}",
        "-" * 28,
    ]
    for inv in items:
        sku = str(inv.product.sku)[:9]
        brand = _clean_brand(getattr(inv.product, "brand", None))
        lines.append(f"{sku:<9} {brand:<12} {inv.quantity:>3}")
    return "<pre>" + escape("\n".join(lines)) + "</pre>"


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
    total_pages = max(1, (len(items) + limit - 1) // limit)

    lines = [
        _("stock_title", page=page + 1, total=total_pages),
        _format_inventory_table(page_items, _),
    ]
        
    builder = InlineKeyboardBuilder()
    add_pagination_buttons(builder, len(items), page, limit, "stock:page", _=_)
    
    built_markup = builder.as_markup()
    markup = built_markup if built_markup.inline_keyboard else None
    
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
