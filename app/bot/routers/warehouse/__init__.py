from aiogram import Router

from app.bot.filters import RoleFilter
from app.models.enums import UserRole

from app.bot.routers.warehouse.orders import router as orders_router
from app.bot.routers.warehouse.receive import router as receive_router
from app.bot.routers.warehouse.display import router as display_router
from app.bot.routers.warehouse.stock import router as stock_router

router = Router(name="warehouse")
router.message.filter(RoleFilter(UserRole.WAREHOUSE))
router.callback_query.filter(RoleFilter(UserRole.WAREHOUSE))

router.include_routers(
    orders_router,
    receive_router,
    display_router,
    stock_router,
)
