from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import FinancialTransactionType


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[FinancialTransactionType] = mapped_column(
        Enum(FinancialTransactionType, name="financial_transaction_type", native_enum=False)
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped["Store"] = relationship(back_populates="financial_transactions")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="financial_transactions")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<FinancialTransaction #{self.id} type={self.type.value} "
            f"amount={self.amount} store={self.store_id}>"
        )
