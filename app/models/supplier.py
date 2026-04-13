from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.supplier_invoice import SupplierInvoice
    from app.models.supplier_payment import SupplierPayment


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    invoices: Mapped[list[SupplierInvoice]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )
    payments: Mapped[list[SupplierPayment]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Supplier #{self.id} name={self.name}>"
