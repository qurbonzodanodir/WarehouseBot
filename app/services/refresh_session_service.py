import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_session_token
from app.models.refresh_session import RefreshSession


class RefreshSessionService:
    def __init__(self, session: AsyncSession, *, ttl_days: int):
        self.session = session
        self.ttl_days = ttl_days

    async def create_session(self, user_id: int) -> str:
        raw_token = self._generate_token()
        refresh_session = RefreshSession(
            user_id=user_id,
            token_hash=hash_session_token(raw_token),
            expires_at=self._expires_at(),
            last_used_at=self._now(),
        )
        self.session.add(refresh_session)
        await self.session.flush()
        return raw_token

    async def rotate_session(self, raw_token: str) -> tuple[int, str] | None:
        refresh_session = await self._get_session(raw_token, lock=True)
        if refresh_session is None:
            return None
        if self._is_inactive(refresh_session):
            await self._revoke(refresh_session)
            return None

        new_token = self._generate_token()
        refresh_session.token_hash = hash_session_token(new_token)
        refresh_session.last_used_at = self._now()
        refresh_session.expires_at = self._expires_at()
        await self.session.flush()
        return refresh_session.user_id, new_token

    async def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        refresh_session = await self._get_session(raw_token, lock=True)
        if refresh_session is None:
            return
        await self._revoke(refresh_session)

    async def _get_session(
        self,
        raw_token: str,
        *,
        lock: bool,
    ) -> RefreshSession | None:
        stmt = select(RefreshSession).where(
            RefreshSession.token_hash == hash_session_token(raw_token)
        )
        if lock:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _revoke(self, refresh_session: RefreshSession) -> None:
        if refresh_session.revoked_at is None:
            refresh_session.revoked_at = self._now()
            await self.session.flush()

    def _expires_at(self) -> datetime:
        return self._now() + timedelta(days=self.ttl_days)

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(48)

    def _is_inactive(self, refresh_session: RefreshSession) -> bool:
        now = self._now()
        return (
            refresh_session.revoked_at is not None
            or refresh_session.expires_at <= now
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
