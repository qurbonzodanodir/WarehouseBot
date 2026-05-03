"""add_brands_catalog

Revision ID: c41c7d2b8e31
Revises: 9b3d2c4f1a90
Create Date: 2026-04-27 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c41c7d2b8e31"
down_revision: Union[str, Sequence[str], None] = "9b3d2c4f1a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
    )
    op.create_index("ix_brands_name", "brands", ["name"], unique=True)

    op.execute(
        sa.text(
            """
            INSERT INTO brands (name)
            SELECT DISTINCT TRIM(brand)
            FROM products
            WHERE brand IS NOT NULL AND TRIM(brand) <> ''
            ORDER BY TRIM(brand)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_brands_name", table_name="brands")
    op.drop_table("brands")
