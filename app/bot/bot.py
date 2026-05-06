from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.i18n import I18nMiddleware
from app.bot.routers.common import router as common_router
from app.bot.routers.seller import seller_router
from app.bot.routers.warehouse import router as warehouse_router
from app.core.config import settings

bot_session = None
if settings.telegram_proxy_url:
    bot_session = AiohttpSession(proxy=settings.telegram_proxy_url)

bot = Bot(
    token=settings.bot_token,
    session=bot_session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())

dp.update.outer_middleware(AuthMiddleware())
dp.update.outer_middleware(I18nMiddleware())

dp.include_routers(
    common_router,
    seller_router,
    warehouse_router,
)
