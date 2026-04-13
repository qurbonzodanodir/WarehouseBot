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
    ) -> list[tuple[int, int]]:
        """Send a message to all active users with a given role (optionally in a store) and return [(chat_id, message_id)]."""
        filters = [User.role == role, User.is_active.is_(True)]
        if store_id is not None:
            filters.append(User.store_id == store_id)

        stmt = select(User).where(*filters)
        result = await self.session.execute(stmt)
        users = result.scalars().all()

        chat_message_ids = []
        for user in users:
            try:
                user_lang = user.language_code if user.language_code else "ru"
                user_translator = Translator(user_lang)
                
                actual_text = text(user_translator) if callable(text) else text
                actual_markup = reply_markup(user_translator) if callable(reply_markup) else reply_markup

                msg = await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=actual_text,
                    reply_markup=actual_markup,
                )
                chat_message_ids.append((user.telegram_id, msg.message_id))
            except Exception as exc:
                logger.warning(
                    "Notification send failed: role=%s store_id=%s user_id=%s telegram_id=%s error=%s",
                    role.value,
                    store_id,
                    user.id,
                    user.telegram_id,
                    exc,
                )
        return chat_message_ids

    async def notify_sellers(
        self,
        store_id: int,
        text: Union[str, Callable[[Any], str]],
        reply_markup: Union[InlineKeyboardMarkup, Callable[[Any], InlineKeyboardMarkup], None] = None,
    ) -> list[tuple[int, int]]:
        """Send a message to all active sellers in a given store."""
        return await self._notify_by_role(UserRole.SELLER, store_id, text, reply_markup)

    async def notify_warehouse(
        self,
        text: Union[str, Callable[[Any], str]],
        reply_markup: Union[InlineKeyboardMarkup, Callable[[Any], InlineKeyboardMarkup], None] = None,
    ) -> list[tuple[int, int]]:
        """Send a message to all active warehouse workers."""
        return await self._notify_by_role(UserRole.WAREHOUSE, None, text, reply_markup)

    async def save_order_notifications(
        self,
        order_ids: list[int],
        chat_message_ids: list[tuple[int, int]]
    ) -> None:
        """Save message IDs in DB to later remove their buttons."""
        from app.models.order_notification import OrderNotification
        for chat_id, message_id in chat_message_ids:
            for order_id in order_ids:
                notif = OrderNotification(
                    order_id=order_id,
                    chat_id=chat_id,
                    message_id=message_id
                )
                self.session.add(notif)
        # Flush is handled by the caller

    async def clear_order_notifications(
        self,
        order_id: int,
        new_text: str | None = None
    ) -> None:
        """Fetch saved message IDs for an order, edit them to remove buttons, and delete DB records."""
        from app.models.order_notification import OrderNotification
        import asyncio
        stmt = select(OrderNotification).where(OrderNotification.order_id == order_id)
        result = await self.session.execute(stmt)
        notifs = result.scalars().all()

        chat_message_ids = [(n.chat_id, n.message_id) for n in notifs]
        # Avoid duplicate edits if multiple orders in the same batch share the same message
        unique_chat_message_ids = list(set(chat_message_ids))

        if unique_chat_message_ids:
            asyncio.create_task(self.remove_order_buttons(unique_chat_message_ids, new_text))
            
            # Delete records 
            for n in notifs:
                await self.session.delete(n)

    async def remove_order_buttons(
        self,
        chat_message_ids: list[tuple[int, int]],
        new_text: str | None = None
    ) -> None:
        """Remove inline buttons from specified messages and optionally update text."""
        for chat_id, message_id in chat_message_ids:
            try:
                if new_text:
                    await self.bot.edit_message_text(
                        text=new_text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=None
                    )
                else:
                    await self.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=None
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to remove buttons: chat_id=%s message_id=%s error=%s",
                    chat_id,
                    message_id,
                    exc,
                )
