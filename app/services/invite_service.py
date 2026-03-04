from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.invite_code import InviteCode


async def create_invite(
    session: AsyncSession,
    role: UserRole,
    store_id: int,
) -> InviteCode:
    invite = InviteCode(role=role, store_id=store_id)
    session.add(invite)
    await session.flush()
    return invite


async def get_invite_by_code(
    session: AsyncSession, code: str
) -> InviteCode | None:
    """Look up a valid (unused, not expired) invite code."""
    result = await session.execute(
        select(InviteCode).where(
            InviteCode.code == code,
            InviteCode.is_used.is_(False),
        )
    )
    invite = result.scalar_one_or_none()
    if invite is None or not invite.is_valid:
        return None
    return invite


async def use_invite(
    session: AsyncSession,
    invite: InviteCode,
    user_id: int,
) -> None:
    """Mark an invite code as used."""
    invite.is_used = True
    invite.used_by_id = user_id
