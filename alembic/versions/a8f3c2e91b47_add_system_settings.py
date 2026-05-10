"""add_system_settings

Revision ID: a8f3c2e91b47
Revises: d2e7f4a91c3b
Create Date: 2026-05-10 17:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8f3c2e91b47"
down_revision: Union[str, Sequence[str], None] = "d2e7f4a91c3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed default retail markup = 1.0
    op.execute(
        sa.text(
            """
            INSERT INTO system_settings (key, value)
            VALUES ('retail_markup', '1.0')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("system_settings")
