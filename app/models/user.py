from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    store_id: Mapped[int | None] = mapped_column(
        ForeignKey("stores.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    store: Mapped["Store | None"] = relationship(back_populates="users")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} role={self.role.value}>"
