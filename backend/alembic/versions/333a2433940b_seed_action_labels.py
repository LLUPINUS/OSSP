"""seed action labels

Revision ID: 333a2433940b
Revises: 42047212feb1
Create Date: 2026-05-25 21:38:15.866464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '333a2433940b'
down_revision: Union[str, Sequence[str], None] = '42047212feb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed 4 action labels. Idempotent via ON CONFLICT on the `name` UNIQUE constraint."""
    op.execute(sa.text("""
        INSERT INTO action_labels (name, display_name_ko) VALUES
            ('cutting', '썰기'),
            ('grilling', '굽기'),
            ('stir_frying', '볶기'),
            ('stirring', '젓기')
        ON CONFLICT (name) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM action_labels
        WHERE name IN ('cutting', 'grilling', 'stir_frying', 'stirring')
    """))
