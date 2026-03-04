from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Store


async def list_active_stores(session: AsyncSession) -> list[Store]:
    result = await session.execute(
        select(Store).where(Store.is_active.is_(True)).order_by(Store.id)
    )
    return list(result.scalars().all())


async def create_store(
    session: AsyncSession,
    name: str,
    address: str,
) -> Store:
    store = Store(
        name=name,
        address=address,
        current_debt=Decimal("0"),
        is_active=True,
    )
    session.add(store)
    await session.flush()
    return store
