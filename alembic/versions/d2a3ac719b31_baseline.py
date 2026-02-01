"""baseline

Revision ID: d2a3ac719b31
Revises: d3e035b75465
Create Date: 2026-02-01 14:09:33.503098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a3ac719b31'
down_revision: Union[str, Sequence[str], None] = 'd3e035b75465'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
