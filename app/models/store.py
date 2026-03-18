from decimal import Decimal

from sqlalchemy import Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import StoreType


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500), default="")
    store_type: Mapped[StoreType] = mapped_column(
        Enum(StoreType, name="store_type", native_enum=False),
        default=StoreType.STORE,
    )
    current_debt: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    users: Mapped[list["User"]] = relationship(back_populates="store")  # noqa: F821
    inventory: Mapped[list["Inventory"]] = relationship(  # noqa: F821
        back_populates="store"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="store")  # noqa: F821
    financial_transactions: Mapped[list["FinancialTransaction"]] = relationship(  # noqa: F821
        back_populates="store"
    )
    debt_ledgers: Mapped[list["DebtLedger"]] = relationship(  # noqa: F821
        back_populates="store"
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r}>"
