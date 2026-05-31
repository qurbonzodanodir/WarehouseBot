"""composite_unique_sku_brand

Revision ID: b87f87dd2c01
Revises: 72e9b8f4c1a2
Create Date: 2026-05-31 10:28:23.840179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b87f87dd2c01'
down_revision: Union[str, Sequence[str], None] = '72e9b8f4c1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old unique index on sku (if it exists)
    op.execute('DROP INDEX IF EXISTS ix_products_sku')
    # Recreate the index on sku but not unique
    op.create_index('ix_products_sku', 'products', ['sku'], unique=False)
    # Create the new composite unique constraint
    op.create_unique_constraint('uq_product_sku_brand', 'products', ['sku', 'brand'])


def downgrade() -> None:
    # Drop the composite unique constraint
    op.drop_constraint('uq_product_sku_brand', 'products', type_='unique')
    # Drop the non-unique index
    op.drop_index('ix_products_sku', table_name='products')
    # Recreate the unique index on sku
    op.create_index('ix_products_sku', 'products', ['sku'], unique=True)
