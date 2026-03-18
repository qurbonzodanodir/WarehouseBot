from aiogram import Router

from .common import router as common_router
from .display import router as display_router
from .order import router as order_router
from .report import router as report_router
from .returns import router as returns_router
from .sales import router as sales_router
from .vitrine import router as vitrine_router

from app.bot.filters import RoleFilter
from app.models.enums import UserRole

seller_router = Router(name="seller")

# Restrict ALL seller routers to users with the SELLER role
seller_router.message.filter(RoleFilter(UserRole.SELLER))
seller_router.callback_query.filter(RoleFilter(UserRole.SELLER))

seller_router.include_router(common_router)
seller_router.include_router(order_router)
seller_router.include_router(vitrine_router)
seller_router.include_router(sales_router)
seller_router.include_router(returns_router)
seller_router.include_router(display_router)
seller_router.include_router(report_router)
