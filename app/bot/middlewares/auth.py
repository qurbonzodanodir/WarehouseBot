"""Auth middleware — identifies and injects the user on every update."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.database import async_session_factory
from app.services import UserService

class AuthMiddleware(BaseMiddleware):
    """
    Outer middleware that runs on every incoming update.

    - Looks up the user by telegram_id.
    - If not found → still passes through but with user=None
      (the /start handler will show a "not registered" message).
    - Otherwise stores `user` and `session` in handler data.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract telegram_id from the update
        update: Update = data.get("event_update") or event
        telegram_id = _extract_telegram_id(update)
        if telegram_id is None:
            return  # Cannot identify user — skip

        async with async_session_factory() as session:
            svc = UserService(session)
            user = await svc.get_user_by_telegram_id(telegram_id)

            data["user"] = user  # May be None for unregistered users
            data["session"] = session
            data["telegram_id"] = telegram_id
            return await handler(event, data)


def _extract_telegram_id(update: Update) -> int | None:
    """Try to pull the sender's telegram_id from any update type."""
    if hasattr(update, "message") and update.message:
        return update.message.from_user.id if update.message.from_user else None
    if hasattr(update, "callback_query") and update.callback_query:
        return update.callback_query.from_user.id
    return None
