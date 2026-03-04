from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.user import User


async def _notify_by_role(
    bot: Bot,
    session: AsyncSession,
    role: UserRole,
    store_id: int | None,
    text: str,
    reply_markup=None,
) -> None:
    """Send a message to all active users with a given role (optionally in a store)."""
    filters = [User.role == role, User.is_active.is_(True)]
    if store_id is not None:
        filters.append(User.store_id == store_id)

    stmt = select(User).where(*filters)
    result = await session.execute(stmt)
    users = result.scalars().all()

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=reply_markup,
            )
        except Exception:
            pass  # user might have blocked the bot


async def notify_sellers(
    bot: Bot,
    session: AsyncSession,
    store_id: int,
    text: str,
    reply_markup=None,
) -> None:
    """Send a message to all active sellers in a given store."""
    await _notify_by_role(bot, session, UserRole.SELLER, store_id, text, reply_markup)


async def notify_warehouse(
    bot: Bot,
    session: AsyncSession,
    text: str,
    reply_markup=None,
) -> None:
    """Send a message to all active warehouse workers."""
    await _notify_by_role(bot, session, UserRole.WAREHOUSE, None, text, reply_markup)
