"""add_invite_codes

Revision ID: b9aacd02643f
Revises: 21a7a3b36c8e
Create Date: 2026-03-03 16:31:07.615016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b9aacd02643f'
down_revision: Union[str, Sequence[str], None] = '21a7a3b36c8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reference the existing enum (do NOT create it again)
user_role_enum = postgresql.ENUM(
    'SELLER', 'WAREHOUSE', 'ADMIN', 'OWNER',
    name='user_role',
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('invite_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('role', user_role_enum, nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False),
        sa.Column('used_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.ForeignKeyConstraint(['used_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invite_codes_code'), 'invite_codes', ['code'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_invite_codes_code'), table_name='invite_codes')
    op.drop_table('invite_codes')
