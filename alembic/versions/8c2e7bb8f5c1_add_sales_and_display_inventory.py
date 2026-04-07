"""add sales and display inventory

Revision ID: 8c2e7bb8f5c1
Revises: 31f8493b1970
Create Date: 2026-03-18 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c2e7bb8f5c1"
down_revision: Union[str, Sequence[str], None] = "31f8493b1970"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "display_inventory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "product_id", name="uq_display_store_product"),
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_per_item", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_store_created_at", "sales", ["store_id", "created_at"], unique=False)
    op.create_index("ix_sales_order_id", "sales", ["order_id"], unique=False)

    # Best-effort backfill for currently active display stock.
    op.execute(
        """
        INSERT INTO display_inventory (store_id, product_id, quantity)
        SELECT
            store_id,
            product_id,
            SUM(
                CASE
                    WHEN status = 'DISPLAY_DELIVERED' THEN quantity
                    WHEN status IN ('DISPLAY_RETURN_PENDING', 'DISPLAY_RETURNED') THEN -quantity
                    ELSE 0
                END
            ) AS quantity
        FROM orders
        GROUP BY store_id, product_id
        HAVING SUM(
            CASE
                WHEN status = 'DISPLAY_DELIVERED' THEN quantity
                WHEN status IN ('DISPLAY_RETURN_PENDING', 'DISPLAY_RETURNED') THEN -quantity
                ELSE 0
            END
        ) > 0
        """
    )

    # Best-effort backfill for historical sales.
    # We preserve quantity and timestamps, but historical price is approximated from current product price
    # because legacy schema did not store a dedicated sale snapshot for manual vitrine sales.
    op.execute(
        """
        INSERT INTO sales (
            store_id,
            product_id,
            order_id,
            user_id,
            quantity,
            price_per_item,
            total_amount,
            created_at
        )
        SELECT
            sm.from_store_id,
            sm.product_id,
            NULL,
            sm.user_id,
            sm.quantity,
            p.price,
            p.price * sm.quantity,
            sm.created_at
        FROM stock_movements sm
        JOIN products p ON p.id = sm.product_id
        WHERE sm.movement_type = 'SALE'
          AND sm.from_store_id IS NOT NULL
          AND sm.user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sales_order_id", table_name="sales")
    op.drop_index("ix_sales_store_created_at", table_name="sales")
    op.drop_table("sales")
    op.drop_table("display_inventory")
