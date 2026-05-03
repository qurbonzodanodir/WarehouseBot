from pydantic import BaseModel
from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionResponse(BaseModel):
    user: "UserMe"


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class UserMe(BaseModel):
    id: int
    telegram_id: int | None
    email: str | None
    name: str
    role: UserRole
    store_id: int | None
    store_name: str | None

    model_config = {"from_attributes": True}
