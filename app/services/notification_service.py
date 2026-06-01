import json
import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pywebpush import webpush, WebPushException

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
        push_title: str | None = None,
    ) -> list[tuple[int, int]]:
        """Send a message to all active warehouse workers, and a Web Push to WAREHOUSE/ADMIN/OWNER."""
        # Send Telegram message to Warehouse workers
        chat_msg_ids = await self._notify_by_role(UserRole.WAREHOUSE, None, text, reply_markup)

        import re
        raw_text = text(Translator("ru")) if callable(text) else text
        
        # Strip HTML tags
        clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
        
        # Determine title and body for the push notification
        lines = clean_text.split('\n')
        if not push_title and len(lines) > 1 and len(lines[0]) < 60:
            # Use the first line as title if it's relatively short
            push_title = lines[0].strip()
            # The rest is the body
            push_body = '\n'.join(lines[1:]).strip()
        else:
            push_title = push_title or "Уведомление от склада"
            push_body = clean_text

        # Send Web Push to Warehouse, Admin, and Owner
        await self._send_web_push_to_roles(
            roles=[UserRole.WAREHOUSE, UserRole.ADMIN, UserRole.OWNER],
            title=push_title,
            body=push_body,
            url="/orders" # Default URL to open when clicked
        )

        return chat_msg_ids

    async def _send_web_push_to_roles(self, roles: list[UserRole], title: str, body: str, url: str | None = None) -> None:
        from app.models.push_subscription import PushSubscription
        from app.core.config import settings

        if not settings.vapid_private_key:
            return

        stmt = select(PushSubscription).join(User).where(User.role.in_(roles), User.is_active.is_(True))
        result = await self.session.execute(stmt)
        subscriptions = result.scalars().all()

        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url
        })

        import asyncio

        dead_sub_ids: list[int] = []

        def _send(sub: PushSubscription) -> bool:
            """Returns True if subscription is dead and should be deleted."""
            try:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                }
                webpush(
                    subscription_info=sub_info,
                    data=payload,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": "mailto:admin@yasham.tj"},
                    ttl=86400,
                    headers={"Urgency": "high"}
                )
                return False
            except WebPushException as ex:
                response = ex.response
                if response is not None and response.status_code in (410, 404):
                    # 410 Gone = subscription expired/unsubscribed, 404 = not found
                    logger.info(f"Removing dead push subscription id={sub.id} (status={response.status_code})")
                    return True
                logger.error(f"Web Push failed: {ex}")
                return False

        for sub in subscriptions:
            is_dead = await asyncio.to_thread(_send, sub)
            if is_dead:
                dead_sub_ids.append(sub.id)

        # Delete dead subscriptions from DB
        if dead_sub_ids:
            from sqlalchemy import delete
            await self.session.execute(
                delete(PushSubscription).where(PushSubscription.id.in_(dead_sub_ids))
            )
            await self.session.commit()

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
