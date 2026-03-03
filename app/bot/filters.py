from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from app.models.enums import UserRole


class RoleFilter(BaseFilter):

    def __init__(self, *roles: UserRole) -> None:
        self.roles = roles

    async def __call__(
        self, event: Message | CallbackQuery, user=None, **kwargs
    ) -> bool:
        if user is None:
            return False
        return user.role in self.roles
