"""drop_products_brand_default

Revision ID: 9b3d2c4f1a90
Revises: 7c8a5d1ef9ab
Create Date: 2026-04-27 10:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b3d2c4f1a90"
down_revision: Union[str, Sequence[str], None] = "7c8a5d1ef9ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("products", "brand", server_default=None)


def downgrade() -> None:
    op.alter_column("products", "brand", server_default=sa.text("'UNKNOWN'"))
