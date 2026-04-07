from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.product import Product
    from app.models.order import Order
    from app.models.user import User
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    price_per_item: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped[Store] = relationship(back_populates="sales")
    product: Mapped[Product] = relationship()
    order: Mapped[Order | None] = relationship()
    user: Mapped[User] = relationship(back_populates="sales")

    def __repr__(self) -> str:
        return (
            f"<Sale #{self.id} store={self.store_id} product={self.product_id} "
            f"qty={self.quantity} amount={self.total_amount}>"
        )
