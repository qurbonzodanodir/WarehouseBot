from datetime import datetime
from pydantic import BaseModel
from app.models.enums import UserRole

class InviteCreate(BaseModel):
    store_id: int
    role: UserRole

class InviteOut(BaseModel):
    code: str
    role: UserRole
    store_id: int
    expires_at: datetime
    is_used: bool
    created_at: datetime

    class Config:
        from_attributes = True
