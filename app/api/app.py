import logging
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Request

from app.bot.bot import bot, dp
from app.core.config import settings

from fastapi.middleware.cors import CORSMiddleware
from web.backend.routers import auth, orders, products, inventory, analytics, stores, finance, invites, suppliers, settings as settings_router

logger = logging.getLogger(__name__)


async def _set_webhook():
    """Register Telegram webhook without blocking API startup."""
    import asyncio

    try:
        await asyncio.wait_for(
            bot.set_webhook(settings.webhook_url, drop_pending_updates=True),
            timeout=10,
        )
        logger.info("Webhook set: %s", settings.webhook_url)
    except Exception as e:
        logger.warning("Failed to set webhook (Telegram unreachable?): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    polling_task = None
    webhook_task = None
    if settings.webhook_host:
        webhook_task = asyncio.create_task(_set_webhook())
    else:
        try:
            await asyncio.wait_for(
                bot.delete_webhook(drop_pending_updates=True),
                timeout=10,
            )
            logger.info("Webhook deleted successfully")
        except Exception as e:
            logger.warning("Failed to delete webhook (Telegram unreachable?): %s. Continuing with polling.", e)
        logger.info("Starting long polling")
        polling_task = asyncio.create_task(_start_polling())

    yield

    if not settings.webhook_host:
        if polling_task:
            polling_task.cancel()
    elif webhook_task:
        webhook_task.cancel()
    try:
        await bot.session.close()
    except Exception:
        pass


async def _start_polling():
    """Run Aiogram polling (used when no webhook is configured)."""
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error("Polling error: %s", e)


app = FastAPI(
    title="Warehouse ERP & Bot API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Web Routers
API_PREFIX = "/api"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(inventory.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(stores.router, prefix=API_PREFIX)
app.include_router(finance.router, prefix=API_PREFIX)
app.include_router(invites.router, prefix=API_PREFIX)
app.include_router(suppliers.router, prefix=API_PREFIX)
app.include_router(settings_router.router, prefix=API_PREFIX)


@app.post(settings.webhook_path)
async def telegram_webhook(request: Request) -> dict:
    """Receive updates from Telegram via webhook."""
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "warehouse-combined-api"}
