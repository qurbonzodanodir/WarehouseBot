from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import UserRole
from app.models.invite_code import InviteCode


class InviteService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_invite(self, role: UserRole, store_id: int) -> InviteCode:
        invite = InviteCode(role=role, store_id=store_id)
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def get_invite_by_code(self, code: str) -> InviteCode | None:
        """Look up a valid (unused, not expired) invite code."""
        result = await self.session.execute(
            select(InviteCode)
            .options(selectinload(InviteCode.store))
            .where(
                InviteCode.code == code,
                InviteCode.is_used.is_(False),
            )
            .with_for_update()
        )
        invite = result.scalar_one_or_none()
        if invite is None or not invite.is_valid:
            return None
        return invite

    async def use_invite(self, invite: InviteCode, user_id: int) -> None:
        """Mark an invite code as used."""
        if invite.is_used:
            raise ValueError("Invite code already used")
        invite.is_used = True
        invite.used_by_id = user_id
