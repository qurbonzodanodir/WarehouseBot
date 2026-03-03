from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.user import User


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> User | None:
    stmt = (
        select(User)
        .options(joinedload(User.store))
        .where(User.telegram_id == telegram_id, User.is_active.is_(True))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_users(
    session: AsyncSession,
    store_id: int | None = None,
) -> list[User]:
    stmt = select(User).where(User.is_active.is_(True))
    if store_id is not None:
        stmt = stmt.where(User.store_id == store_id)
    stmt = stmt.order_by(User.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())
