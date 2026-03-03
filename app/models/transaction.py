from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TransactionType


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped["Store"] = relationship(back_populates="transactions")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="transactions")  # noqa: F821
    product: Mapped["Product | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Transaction #{self.id} type={self.type.value} "
            f"amount={self.amount} store={self.store_id}>"
        )
