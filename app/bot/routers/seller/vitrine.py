from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from app.models.user import User
from app.bot.routers.seller.catalog_ui import send_catalog_page

router = Router(name="seller.vitrine")


async def _send_vitrine_page(
    message_or_callback: Message | CallbackQuery, items: list, page: int, _: Any
) -> None:
    if not items:
        text = _("vitrine_empty")
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.edit_text(text)
        return

    await send_catalog_page(
        message_or_callback,
        _("vitrine_title"),
        items,
        page,
        callback_prefix="vitrine:page",
        item_callback_prefix="ignore",
        _=_,
        selectable=False,
    )


@router.message(F.text.in_({"🖼 Витрина", "🖼 Рафи фурӯш"}))
async def my_inventory(
    message: Message, user: User, session: AsyncSession, state: FSMContext, _: Any
) -> None:
    await state.clear()
    from app.services import OrderService
    order_svc = OrderService(session)
    items = await order_svc.get_store_vitrine_inventory(user.store_id)
    await _send_vitrine_page(message, items, page=0, _=_)


@router.callback_query(F.data.startswith("vitrine:page:"))
async def vitrine_page_nav(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    from app.services import OrderService
    order_svc = OrderService(session)
    items = await order_svc.get_store_vitrine_inventory(user.store_id)
    await _send_vitrine_page(callback, items, page, _=_)
    await callback.answer()
