from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from web.backend.dependencies import SessionDep, CurrentUser
from app.core.config import settings
from app.models.user import User
from app.models.push_subscription import PushSubscription

router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushKeys


@router.get("/vapid-public-key")
async def get_vapid_public_key() -> dict[str, str | None]:
    return {"publicKey": settings.vapid_public_key}


@router.post("/subscribe")
async def subscribe_push(
    sub: PushSubscriptionCreate,
    db: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    # Check if subscription already exists
    stmt = select(PushSubscription).where(PushSubscription.endpoint == sub.endpoint)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.user_id = current_user.id
        existing.p256dh = sub.keys.p256dh
        existing.auth = sub.keys.auth
        await db.commit()
        return {"status": "ok"}

    new_sub = PushSubscription(
        user_id=current_user.id,
        endpoint=sub.endpoint,
        p256dh=sub.keys.p256dh,
        auth=sub.keys.auth,
    )
    db.add(new_sub)
    await db.commit()

    return {"status": "ok"}
