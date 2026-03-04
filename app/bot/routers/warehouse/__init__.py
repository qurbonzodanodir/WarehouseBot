from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.filters import RoleFilter
from app.models.enums import UserRole

from app.bot.routers.warehouse.orders import router as orders_router
from app.bot.routers.warehouse.receive import router as receive_router
from app.bot.routers.warehouse.display import router as display_router
from app.bot.routers.warehouse.stock import router as stock_router

router = Router(name="warehouse")
router.message.filter(RoleFilter(UserRole.WAREHOUSE))
router.callback_query.filter(RoleFilter(UserRole.WAREHOUSE))

from app.bot.keyboards.reply import WAREHOUSE_MENU, WAREHOUSE_MORE_MENU


@router.message(F.text == "Ещё 🔽")
async def wh_show_more_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Дополнительные опции:", reply_markup=WAREHOUSE_MORE_MENU)


@router.message(F.text == "🔙 Назад")
async def wh_back_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=WAREHOUSE_MENU)


router.include_routers(
    orders_router,
    receive_router,
    display_router,
    stock_router,
)
