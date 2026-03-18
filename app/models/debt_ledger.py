from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DebtLedgerReason


class DebtLedger(Base):
    __tablename__ = "debt_ledgers"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    amount_change: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # + = debt increased, - = debt decreased
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[DebtLedgerReason] = mapped_column(
        Enum(DebtLedgerReason, name="debt_ledger_reason", native_enum=False)
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True) # E.g., "Sale Order #123"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped["Store"] = relationship(back_populates="debt_ledgers")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<DebtLedger store={self.store_id} change={self.amount_change} "
            f"balance={self.balance_after}>"
        )
