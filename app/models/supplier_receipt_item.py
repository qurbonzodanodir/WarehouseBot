from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.supplier_receipt import SupplierReceipt


class SupplierReceiptLineItem(Base):
    """A single product line in a partner receipt."""

    __tablename__ = "supplier_receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("supplier_receipts.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    receipt: Mapped[SupplierReceipt] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    @property
    def line_total(self) -> Decimal:
        return self.price_per_unit * self.quantity

    def __repr__(self) -> str:
        return f"<SupplierReceiptLineItem receipt={self.receipt_id} product={self.product_id} qty={self.quantity}>"
