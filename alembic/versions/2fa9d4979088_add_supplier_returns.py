"""add_supplier_returns

Revision ID: 2fa9d4979088
Revises: 25444190f66e
Create Date: 2026-04-14 10:14:18.706469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fa9d4979088'
down_revision: Union[str, Sequence[str], None] = '25444190f66e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'supplier_returns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('supplier_id', sa.Integer(), sa.ForeignKey('suppliers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_table(
        'supplier_return_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('return_id', sa.Integer(), sa.ForeignKey('supplier_returns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price_per_unit', sa.Numeric(12, 2), nullable=False),
    )



def downgrade() -> None:
    op.drop_table('supplier_return_items')
    op.drop_table('supplier_returns')
