from decimal import Decimal

from fastapi import APIRouter, HTTPException, status

from app.models.enums import UserRole
from app.services.settings_service import SettingsService
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=SettingsOut, summary="Получить системные настройки")
async def get_settings(
    session: SessionDep,
    current_user: CurrentUser,
) -> SettingsOut:
    svc = SettingsService(session)
    markup = await svc.get_retail_markup()
    return SettingsOut(retail_markup=markup)


@router.patch("", response_model=SettingsOut, summary="Обновить системные настройки (Owner)")
async def update_settings(
    body: SettingsUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> SettingsOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    svc = SettingsService(session)

    if body.retail_markup is not None:
        await svc.set("retail_markup", str(Decimal(body.retail_markup)))

    await session.commit()

    markup = await svc.get_retail_markup()
    return SettingsOut(retail_markup=markup)
