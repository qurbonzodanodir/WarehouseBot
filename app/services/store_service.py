from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StoreType
from app.models.store import Store


class StoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active_stores(self) -> list[Store]:
        """Return only RETAIL stores (not the warehouse)."""
        result = await self.session.execute(
            select(Store).where(
                Store.is_active.is_(True),
                Store.store_type == StoreType.STORE,
            ).order_by(Store.id)
        )
        return list(result.scalars().all())

    async def create_store(self, name: str, address: str) -> Store:
        """Create a new retail store (never a warehouse)."""
        store = Store(
            name=name,
            address=address,
            store_type=StoreType.STORE,
            current_debt=Decimal("0"),
            is_active=True,
        )
        self.session.add(store)
        await self.session.flush()
        return store

    async def update_store(self, store_id: int, name: str = None, address: str = None) -> Store | None:
        store = await self.session.get(Store, store_id)
        if not store:
            return None
        if name is not None:
            store.name = name
        if address is not None:
            store.address = address
        await self.session.flush()
        return store

    async def delete_store(self, store_id: int) -> bool:
        store = await self.session.get(Store, store_id)
        if not store:
            return False
        store.is_active = False
        await self.session.flush()
        return True

    async def get_main_warehouse_id(self) -> int | None:
        """Find the main warehouse by store_type = WAREHOUSE."""
        result = await self.session.execute(
            select(Store.id).where(
                Store.is_active.is_(True),
                Store.store_type == StoreType.WAREHOUSE,
            ).limit(1)
        )
        return result.scalar_one_or_none()
