"""merge_all_heads

Revision ID: f9e187209bbb
Revises: 20261020_006_c4, c2_005_experiments_and_baselines, c1_0006, f1a89c2b4d3e
Create Date: 2026-10-20 20:37:09.265052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9e187209bbb'
down_revision: Union[str, Sequence[str], None] = ('20261020_006_c4', 'c2_005_experiments_and_baselines', 'c1_0006', 'f1a89c2b4d3e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
