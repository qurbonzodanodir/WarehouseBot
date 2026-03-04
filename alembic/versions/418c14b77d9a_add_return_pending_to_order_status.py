"""add return_pending to order status

Revision ID: 418c14b77d9a
Revises: 8c65a0f67c21
Create Date: 2026-03-04 12:49:44.240947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '418c14b77d9a'
down_revision: Union[str, Sequence[str], None] = '8c65a0f67c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'return_pending'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'RETURN_PENDING'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
