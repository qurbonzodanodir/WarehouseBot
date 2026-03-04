from aiogram import Router

from app.bot.filters import RoleFilter
from app.models.enums import UserRole

from app.bot.routers.owner.dashboard import router as dashboard_router
from app.bot.routers.owner.collection import router as collection_router
from app.bot.routers.owner.catalog import router as catalog_router
from app.bot.routers.owner.management import router as management_router

router = Router(name="owner")
router.message.filter(RoleFilter(UserRole.OWNER))

router.include_routers(
    dashboard_router,
    collection_router,
    catalog_router,
    management_router,
)
