from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.core.config import settings
from app.models.enums import UserRole
from web.backend.dependencies import (
    ACCESS_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    CurrentUser,
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SessionDep,
    create_access_token,
)
from web.backend.schemas.auth import LoginRequest, SessionResponse, UserMe

from app.core.security import verify_password
from app.services.refresh_session_service import RefreshSessionService

router = APIRouter(prefix="/auth", tags=["Auth"])


def _to_user_me(user: User) -> UserMe:
    return UserMe(
        id=user.id,
        telegram_id=user.telegram_id,
        email=user.email,
        name=user.name,
        role=user.role,
        store_id=user.store_id,
        store_name=user.store.name if user.store else None,
    )


async def _get_user_with_store(session: SessionDep, user_id: int) -> User | None:
    stmt = select(User).options(selectinload(User.store)).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _cookie_secure(request: Request | None = None) -> bool:
    if request is not None:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        if forwarded_proto:
            return forwarded_proto == "https"
        return request.url.scheme == "https"
    return settings.frontend_url.startswith("https://")


def _set_session_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    request: Request | None = None,
) -> None:
    secure = _cookie_secure(request)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", samesite="lax")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/", samesite="lax")


@router.post(
    "/login",
    response_model=SessionResponse,
    summary="Войти по Email",
    description="Принимает email и пароль. Создаёт сессию и возвращает пользователя.",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> SessionResponse:
    stmt = select(User).options(selectinload(User.store)).where(User.email == body.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    if user.role == UserRole.SELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У продавцов нет доступа к веб-панели",
        )

    token = create_access_token(str(user.id))
    refresh_token = await RefreshSessionService(
        session,
        ttl_days=REFRESH_TOKEN_EXPIRE_DAYS,
    ).create_session(user.id)
    await session.commit()
    _set_session_cookies(response, token, refresh_token, request)

    return SessionResponse(user=_to_user_me(user))


@router.get(
    "/me",
    response_model=UserMe,
    summary="Текущий пользователь",
)
async def get_me(session: SessionDep, current_user: CurrentUser) -> UserMe:
    user = await _get_user_with_store(session, current_user.id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return _to_user_me(user)


@router.post(
    "/refresh",
    response_model=SessionResponse,
    summary="Обновить access токен",
    description="Обновляет сессию по refresh cookie и возвращает актуального пользователя.",
)
async def refresh_token(
    request: Request,
    response: Response,
    session: SessionDep,
) -> SessionResponse:
    refresh_token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    refresh_session_service = RefreshSessionService(
        session,
        ttl_days=REFRESH_TOKEN_EXPIRE_DAYS,
    )
    rotated = await refresh_session_service.rotate_session(refresh_token_value)
    if rotated is None:
        await session.commit()
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id, new_refresh_token = rotated
    user = await _get_user_with_store(session, user_id)
    if not user or not user.is_active:
        await refresh_session_service.revoke_session(new_refresh_token)
        await session.commit()
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(str(user.id))
    await session.commit()
    _set_session_cookies(response, access_token, new_refresh_token, request)

    return SessionResponse(user=_to_user_me(user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Завершить сессию",
)
async def logout(request: Request, response: Response, session: SessionDep) -> Response:
    refresh_token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    await RefreshSessionService(
        session,
        ttl_days=REFRESH_TOKEN_EXPIRE_DAYS,
    ).revoke_session(refresh_token_value)
    await session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    _clear_session_cookies(response)
    return response
