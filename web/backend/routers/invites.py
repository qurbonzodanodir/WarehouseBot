from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.invites import InviteCreate, InviteOut
from app.models.invite_code import InviteCode
from app.models.store import Store
from app.models.enums import StoreType, UserRole
from app.services.invite_service import InviteService

router = APIRouter(prefix="/invites", tags=["Invites"])


def _validate_role_for_store(store: Store, role: UserRole) -> None:
    if store.store_type == StoreType.WAREHOUSE and role != UserRole.WAREHOUSE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для склада можно создавать приглашение только для роли Складщик",
        )
    if store.store_type == StoreType.STORE and role != UserRole.SELLER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для магазина можно создавать приглашение только для роли Продавец",
        )

@router.post("", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: InviteCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can create invites")

    # Check store exists
    store = await session.get(Store, body.store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    _validate_role_for_store(store, body.role)

    invite_svc = InviteService(session)
    invite = await invite_svc.create_invite(role=body.role, store_id=body.store_id)
    await session.commit()
    await session.refresh(invite)
    return invite

@router.get("/{store_id}", response_model=list[InviteOut])
async def list_invites(
    store_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can view invites")

    result = await session.execute(
        select(InviteCode)
        .where(InviteCode.store_id == store_id, InviteCode.is_used.is_(False))
        .order_by(InviteCode.created_at.desc())
    )
    invites = result.scalars().all()
    
    # Filter valid ones
    return [i for i in invites if i.is_valid]

@router.delete("/{code}")
async def delete_invite(
    code: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete invites")

    result = await session.execute(
        select(InviteCode).where(InviteCode.code == code)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    await session.delete(invite)
    await session.commit()
    return {"status": "success"}
