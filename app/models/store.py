from __future__ import annotations
from app.models.enums import StoreType, db_enum
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.inventory import Inventory
    from app.models.display_inventory import DisplayInventory
    from app.models.order import Order
    from app.models.sale import Sale
    from app.models.financial_transaction import FinancialTransaction
    from app.models.debt_ledger import DebtLedger

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500), default="")
    store_type: Mapped[StoreType] = mapped_column(
        db_enum(StoreType, "store_type"),
        default=StoreType.STORE,
    )
    current_debt: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    users: Mapped[list[User]] = relationship(back_populates="store")
    inventory: Mapped[list[Inventory]] = relationship(
        back_populates="store"
    )
    display_inventory: Mapped[list[DisplayInventory]] = relationship(
        back_populates="store"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="store")
    sales: Mapped[list[Sale]] = relationship(back_populates="store")
    financial_transactions: Mapped[list[FinancialTransaction]] = relationship(
        back_populates="store"
    )
    debt_ledgers: Mapped[list[DebtLedger]] = relationship(
        back_populates="store"
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r}>"
