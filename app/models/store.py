from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500), default="")
    current_debt: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    users: Mapped[list["User"]] = relationship(back_populates="store")  # noqa: F821
    inventory: Mapped[list["Inventory"]] = relationship(  # noqa: F821
        back_populates="store"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="store")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="store"
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r}>"
