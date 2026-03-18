from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.enums import UserRole


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.store))
            .where(User.telegram_id == telegram_id, User.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_user(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def update_user(
        self, 
        user_id: int, 
        role: UserRole = None, 
        store_id: int = None,
        is_active: bool = None
    ) -> User | None:
        """Update user details."""
        user = await self.session.get(User, user_id)
        if not user:
            return None
        
        if role is not None:
            user.role = role
        if store_id is not None:
            user.store_id = store_id
        if is_active is not None:
            user.is_active = is_active
            
        await self.session.flush()
        return user

    async def delete_user(self, user_id: int) -> bool:
        """Soft-delete a user by setting is_active=False."""
        user = await self.session.get(User, user_id)
        if not user:
            return False
        
        user.is_active = False
        await self.session.flush()
        return True
