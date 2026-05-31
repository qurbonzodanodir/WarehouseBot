import asyncio
from app.core.database import async_session_maker
from app.models.store import Store
from sqlalchemy import select, update

async def main():
    async with async_session_maker() as session:
        # Update debt for Nekruz
        stmt = update(Store).where(Store.name.ilike('%Некруз%')).values(current_debt=Store.current_debt + 575)
        await session.execute(stmt)
        await session.commit()
        print("Updated debt for Nekruz by 575 TJS")

asyncio.run(main())
