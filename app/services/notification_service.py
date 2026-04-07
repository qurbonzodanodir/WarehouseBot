import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import UserRole
from app.models.user import User
from typing import Any, Callable, Union
from aiogram.types import InlineKeyboardMarkup
from app.core.i18n import Translator


logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot, session: AsyncSession):
        self.bot = bot
        self.session = session

    async def _notify_by_role(
        self,
        role: UserRole,
        store_id: int | None,
        text: Union[str, Callable[[Any], str]],
        reply_markup: Union[InlineKeyboardMarkup, Callable[[Any], InlineKeyboardMarkup], None] = None,
    ) -> None:
        """Send a message to all active users with a given role (optionally in a store)."""
        filters = [User.role == role, User.is_active.is_(True)]
        if store_id is not None:
            filters.append(User.store_id == store_id)

        stmt = select(User).where(*filters)
        result = await self.session.execute(stmt)
        users = result.scalars().all()

        for user in users:
            try:
                user_lang = user.language_code if user.language_code else "ru"
                user_translator = Translator(user_lang)
                
                actual_text = text(user_translator) if callable(text) else text
                actual_markup = reply_markup(user_translator) if callable(reply_markup) else reply_markup

                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=actual_text,
                    reply_markup=actual_markup,
                )
            except Exception as exc:
                logger.warning(
                    "Notification send failed: role=%s store_id=%s user_id=%s telegram_id=%s error=%s",
                    role.value,
                    store_id,
                    user.id,
                    user.telegram_id,
                    exc,
                )

    async def notify_sellers(
        self,
        store_id: int,
        text: Union[str, Callable[[Any], str]],
        reply_markup: Union[InlineKeyboardMarkup, Callable[[Any], InlineKeyboardMarkup], None] = None,
    ) -> None:
        """Send a message to all active sellers in a given store."""
        await self._notify_by_role(UserRole.SELLER, store_id, text, reply_markup)

    async def notify_warehouse(
        self,
        text: Union[str, Callable[[Any], str]],
        reply_markup: Union[InlineKeyboardMarkup, Callable[[Any], InlineKeyboardMarkup], None] = None,
    ) -> None:
        """Send a message to all active warehouse workers."""
        await self._notify_by_role(UserRole.WAREHOUSE, None, text, reply_markup)
