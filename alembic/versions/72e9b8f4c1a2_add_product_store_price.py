"""add product store price

Revision ID: 72e9b8f4c1a2
Revises: 5b7c2d9a1e33
Create Date: 2026-05-12 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "72e9b8f4c1a2"
down_revision: str | Sequence[str] | None = "5b7c2d9a1e33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("store_price", sa.Numeric(precision=10, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "store_price")
