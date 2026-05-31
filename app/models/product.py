from decimal import Decimal

from sqlalchemy import Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), index=True)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    store_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("sku", "brand", name="uq_product_sku_brand"),
    )

    @property
    def effective_store_price(self) -> Decimal:
        return self.store_price if self.store_price is not None else self.price

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku!r}>"
