from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.sale import Sale
    from app.models.financial_transaction import FinancialTransaction

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

    store: Mapped[Store | None] = relationship(back_populates="users")
    sales: Mapped[list[Sale]] = relationship(back_populates="user")
    financial_transactions: Mapped[list[FinancialTransaction]] = relationship(
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} role={self.role.value}>"
