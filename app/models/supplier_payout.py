from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.user import User


class SupplierPayout(Base):
    """Records a payment made to a partner (our debt decreases)."""

    __tablename__ = "supplier_payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    supplier: Mapped[Supplier] = relationship(back_populates="payouts")
    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"<SupplierPayout #{self.id} supplier={self.supplier_id} amount={self.amount}>"
