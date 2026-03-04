"""add sold and returned to order status

Revision ID: 8c65a0f67c21
Revises: 63ccf976ab61
Create Date: 2026-03-04 12:28:55.549242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c65a0f67c21'
down_revision: Union[str, Sequence[str], None] = '63ccf976ab61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'sold'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'returned'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
