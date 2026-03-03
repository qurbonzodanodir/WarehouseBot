import logging
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Request

from app.bot.bot import bot, dp
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.webhook_host:
        await bot.set_webhook(
            settings.webhook_url,
            drop_pending_updates=True,
        )
        logger.info("Webhook set: %s", settings.webhook_url)
    else:
        logger.info("No WEBHOOK_HOST set — starting long polling")
        await bot.delete_webhook(drop_pending_updates=True)
        import asyncio

        polling_task = asyncio.create_task(_start_polling())

    yield

    if settings.webhook_host:
        await bot.delete_webhook()
    else:
        polling_task.cancel()
    await bot.session.close()


async def _start_polling():
    """Run Aiogram polling (used when no webhook is configured)."""
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error("Polling error: %s", e)


app = FastAPI(
    title="Warehouse Bot API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post(settings.webhook_path)
async def telegram_webhook(request: Request) -> dict:
    """Receive updates from Telegram via webhook."""
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
