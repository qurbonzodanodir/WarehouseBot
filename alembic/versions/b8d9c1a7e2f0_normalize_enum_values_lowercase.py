"""normalize_enum_values_lowercase

Revision ID: b8d9c1a7e2f0
Revises: ff4d7879f689
Create Date: 2026-04-07 11:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8d9c1a7e2f0"
down_revision: Union[str, Sequence[str], None] = "ff4d7879f689"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table_name, column_name in (
        ("stores", "store_type"),
        ("users", "role"),
        ("orders", "status"),
        ("stock_movements", "movement_type"),
        ("financial_transactions", "type"),
        ("debt_ledgers", "reason"),
        ("invite_codes", "role"),
    ):
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET {column_name} = lower({column_name}) "
                f"WHERE {column_name} IS NOT NULL"
            )
        )


def downgrade() -> None:
    # Not reversible safely because casing normalization is lossy.
    pass
