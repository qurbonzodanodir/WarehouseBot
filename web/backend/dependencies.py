from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.user import User
from app.services.user_service import UserService

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ──────────────────────────────────────────────────────────────────────────────
# DB Session dependency
# ──────────────────────────────────────────────────────────────────────────────
async def get_session() -> AsyncSession:  # type: ignore[return]
    async with async_session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ──────────────────────────────────────────────────────────────────────────────
# JWT helpers
# ──────────────────────────────────────────────────────────────────────────────
def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """Decode JWT and return user id. Raises HTTPException on failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        return int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception


# ──────────────────────────────────────────────────────────────────────────────
# Current user dependency
# ──────────────────────────────────────────────────────────────────────────────
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    user_id = decode_token(token)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


from app.models.enums import UserRole

# ──────────────────────────────────────────────────────────────────────────────
# Role Checkers
# ──────────────────────────────────────────────────────────────────────────────
class RoleChecker:
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас недостаточно прав для выполнения этой операции",
            )
        return user


# Specialized dependencies
AdminUser = Annotated[User, Depends(RoleChecker([UserRole.ADMIN, UserRole.OWNER]))]
OwnerUser = Annotated[User, Depends(RoleChecker([UserRole.OWNER]))]
WarehouseUser = Annotated[User, Depends(RoleChecker([UserRole.WAREHOUSE, UserRole.OWNER]))]
SellerUser = Annotated[User, Depends(RoleChecker([UserRole.SELLER, UserRole.OWNER]))]

