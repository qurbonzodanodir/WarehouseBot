"""Add manual debt transactions

Revision ID: e4a1c9d7b230
Revises: b750b0983bdf
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4a1c9d7b230"
down_revision: Union[str, Sequence[str], None] = "b750b0983bdf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manual_debt_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "charge",
                "payment",
                name="manual_debt_transaction_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_manual_debt_transactions_store_id",
        "manual_debt_transactions",
        ["store_id"],
    )
    op.create_index(
        "ix_manual_debt_transactions_operation_date",
        "manual_debt_transactions",
        ["operation_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_manual_debt_transactions_operation_date",
        table_name="manual_debt_transactions",
    )
    op.drop_index(
        "ix_manual_debt_transactions_store_id",
        table_name="manual_debt_transactions",
    )
    op.drop_table("manual_debt_transactions")
