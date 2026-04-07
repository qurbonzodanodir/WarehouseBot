from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DisplayInventory(Base):
    __tablename__ = "display_inventory"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_display_store_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    store: Mapped["Store"] = relationship(back_populates="display_inventory")  # noqa: F821
    product: Mapped["Product"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<DisplayInventory store={self.store_id} "
            f"product={self.product_id} qty={self.quantity}>"
        )
