"""add_brand_to_products

Revision ID: 7c8a5d1ef9ab
Revises: 2fa9d4979088
Create Date: 2026-04-27 10:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c8a5d1ef9ab"
down_revision: Union[str, Sequence[str], None] = "2fa9d4979088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("brand", sa.String(length=120), nullable=False, server_default="UNKNOWN"),
    )
    op.create_index("ix_products_brand", "products", ["brand"], unique=False)

    # Backfill existing products with a simple inferred brand from SKU.
    op.execute(
        sa.text(
            """
            UPDATE products
            SET brand = UPPER(SPLIT_PART(TRIM(sku), ' ', 1))
            WHERE brand IS NULL OR TRIM(brand) = '' OR brand = 'UNKNOWN'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_column("products", "brand")
