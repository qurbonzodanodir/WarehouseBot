from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import StockMovementType, db_enum


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    from_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    to_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[StockMovementType] = mapped_column(
        db_enum(StockMovementType, "stock_movement_type")
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True) # Who performed it
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product: Mapped["Product"] = relationship()  # noqa: F821
    from_store: Mapped["Store | None"] = relationship(foreign_keys=[from_store_id])  # noqa: F821
    to_store: Mapped["Store | None"] = relationship(foreign_keys=[to_store_id])  # noqa: F821
    user: Mapped["User | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<StockMovement #{self.id} type={self.movement_type.value} "
            f"qty={self.quantity} prod={self.product_id}>"
        )
