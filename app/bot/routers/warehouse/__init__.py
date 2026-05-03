from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.filters import RoleFilter
from app.bot.keyboards import reply
from app.models.enums import UserRole

from app.bot.routers.warehouse.orders import router as orders_router
from app.bot.routers.warehouse.stock import router as stock_router

router = Router(name="warehouse")
router.message.filter(RoleFilter(UserRole.WAREHOUSE))
router.callback_query.filter(RoleFilter(UserRole.WAREHOUSE))

@router.message(F.text.in_({"🔙 Назад", "🔙 Ба қафо"}))
async def wh_back_to_main_menu(message: Message, state: FSMContext, _: Any) -> None:
    await state.clear()
    await message.answer(_("main_menu_label"), reply_markup=reply.get_warehouse_menu(_))


router.include_routers(
    orders_router,
    stock_router,
)
