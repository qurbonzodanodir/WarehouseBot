from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.middlewares.auth import AuthMiddleware
from app.bot.routers.common import router as common_router
from app.bot.routers.seller import router as seller_router
from app.bot.routers.warehouse import router as warehouse_router
from app.bot.routers.owner import router as owner_router
from app.core.config import settings

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())

dp.update.outer_middleware(AuthMiddleware())

dp.include_routers(
    common_router,
    seller_router,
    warehouse_router,
    owner_router,
)
