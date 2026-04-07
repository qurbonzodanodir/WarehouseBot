from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole, db_enum


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(db_enum(UserRole, "user_role"))

    store_id: Mapped[int | None] = mapped_column(
        ForeignKey("stores.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    language_code: Mapped[str] = mapped_column(String(5), default="ru")

    store: Mapped["Store | None"] = relationship(back_populates="users")  # noqa: F821
    sales: Mapped[list["Sale"]] = relationship(back_populates="user")  # noqa: F821
    financial_transactions: Mapped[list["FinancialTransaction"]] = relationship(  # noqa: F821
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} role={self.role.value}>"
