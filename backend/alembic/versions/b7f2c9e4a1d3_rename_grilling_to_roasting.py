"""rename action label grilling to roasting

Revision ID: b7f2c9e4a1d3
Revises: c3e8a1d6b2f5
Create Date: 2026-06-05

The CV team's tool->action mapping table renamed the English action label
`grilling` to `roasting` (tongs -> roasting). The Korean display name `굽기`
is unchanged. Matching is done by `display_name_ko` (db_service._resolve_action_label_id),
so this rename is functionally inert today and only aligns the English `name`
with the CV team's vocabulary (for future English-name matching).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f2c9e4a1d3'
down_revision: Union[str, Sequence[str], None] = 'c3e8a1d6b2f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE action_labels SET name='roasting' WHERE name='grilling'"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE action_labels SET name='grilling' WHERE name='roasting'"
    ))
