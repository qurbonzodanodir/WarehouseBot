import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole


def _generate_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(10), unique=True, index=True, default=_generate_code
    )
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    store: Mapped["Store"] = relationship()  # noqa: F821
    used_by: Mapped["User | None"] = relationship()  # noqa: F821

    def __init__(self, **kwargs):
        if "expires_at" not in kwargs:
            kwargs["expires_at"] = datetime.utcnow() + timedelta(hours=24)
        if "code" not in kwargs:
            kwargs["code"] = _generate_code()
        super().__init__(**kwargs)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired

    def __repr__(self) -> str:
        return f"<InviteCode {self.code} role={self.role.value} used={self.is_used}>"
