from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ManualDebtTransactionType, db_enum

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.user import User


class ManualDebtTransaction(Base):
    __tablename__ = "manual_debt_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[ManualDebtTransactionType] = mapped_column(
        db_enum(ManualDebtTransactionType, "manual_debt_transaction_type")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    operation_date: Mapped[date] = mapped_column(Date, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped[Store] = relationship(back_populates="manual_debt_transactions")
    user: Mapped[User] = relationship(back_populates="manual_debt_transactions")
