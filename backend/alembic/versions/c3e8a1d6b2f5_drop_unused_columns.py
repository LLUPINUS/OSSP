"""drop unused columns (recipes.duration_seconds, recipes.language, action_labels.description)

Revision ID: c3e8a1d6b2f5
Revises: 333a2433940b
Create Date: 2026-05-30

These three columns were defined in the initial schema but are never populated
nor read by any code path (MVP scope). Dropping them to keep the schema lean.
The downgrade re-creates them as nullable, matching the original definition.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e8a1d6b2f5'
down_revision: Union[str, Sequence[str], None] = '333a2433940b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('recipes', 'duration_seconds')
    op.drop_column('recipes', 'language')
    op.drop_column('action_labels', 'description')


def downgrade() -> None:
    op.add_column('action_labels', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('recipes', sa.Column('language', sa.String(length=10), nullable=True))
    op.add_column('recipes', sa.Column('duration_seconds', sa.Integer(), nullable=True))
