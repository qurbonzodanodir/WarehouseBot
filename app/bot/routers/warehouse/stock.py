from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from app.models.user import User
from app.services import OrderService
from app.bot.routers.seller.catalog_ui import send_catalog_page

router = Router(name="warehouse.stock")


async def _send_stock_page(
    message_or_callback: Message | CallbackQuery, 
    items: list, 
    page: int,
    _: Any,
) -> None:
    if not items:
        text = _("stock_empty")
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.edit_text(text)
        return

    await send_catalog_page(
        message_or_callback,
        _("stock_title"),
        items,
        page,
        callback_prefix="stock:page",
        item_callback_prefix="ignore",
        _=_,
        selectable=False,
    )


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
