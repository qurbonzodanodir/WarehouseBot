"""Auth middleware — identifies and injects the user on every update."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.database import async_session_factory
from app.services import UserService

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_id = _extract_telegram_id(event)
        if telegram_id is None:
            return await handler(event, data)

        try:
            async with async_session_factory() as session:
                svc = UserService(session)
                user = await svc.get_user_by_telegram_id(telegram_id)

                data["user"] = user
                data["session"] = session
                data["telegram_id"] = telegram_id
                return await handler(event, data)
        except Exception as e:
            logger.error(f"Database error in AuthMiddleware: {e}", exc_info=True)
            # We don't want to crash the bot, but we can't proceed without DB
            if isinstance(event, Update) and event.message:
                await event.message.answer("⚠️ Временные технические неполадки с базой данных. Попробуйте позже.")
            return

def _extract_telegram_id(event: Any) -> int | None:
    """Try to pull the sender's telegram_id from various update types."""
    user = getattr(event, "from_user", None)
    if user:
        return user.id

    # Fallback for complex Update objects
    if isinstance(event, Update):
        for sub in (event.message, event.callback_query, event.inline_query, event.my_chat_member):
            if sub is not None:
                fu = getattr(sub, "from_user", None)
                if fu is not None:
                    return fu.id

    return None
