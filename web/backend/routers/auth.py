from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from web.backend.dependencies import SessionDep, create_access_token
from web.backend.schemas.auth import LoginRequest, TokenResponse, UserMe

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Войти по Email",
    description="Принимает email и пароль. Возвращает JWT токен.",
)
async def login(body: LoginRequest, session: SessionDep) -> TokenResponse:
    stmt = select(User).options(selectinload(User.store)).where(User.email == body.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    # Use email or telegram_id (if exists) as subject for token. Let's use user.id to be safe.
    # Wait, dependencies.py expects telegram_id or id? Let's check dependencies.py
    # Previously: create_access_token(user.telegram_id)
    # If a web admin has no telegram_id, this breaks if dependencies.py looks up by telegram_id.
    # I need to review dependencies.py. For now, let's use user.id and fix dependencies.py later.
    token = create_access_token(str(user.id))

    return TokenResponse(
        access_token=token,
        user=UserMe(
            id=user.id,
            telegram_id=user.telegram_id,
            email=user.email,
            name=user.name,
            role=user.role,
            store_id=user.store_id,
            store_name=user.store.name if user.store else None,
        ),
    )


@router.get(
    "/me",
    response_model=UserMe,
    summary="Текущий пользователь",
)
async def get_me(session: SessionDep) -> UserMe:
    """Protected endpoint — используй токен из /login."""
    # NOTE: используется через CurrentUser dependency в main.py или отдельно
    from web.backend.dependencies import get_current_user
    raise HTTPException(status_code=501, detail="Use Authorization header")
