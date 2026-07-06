"""baseline — schema as built by Base.metadata.create_all

This is a no-op marker revision. The initial schema is bootstrapped on a
fresh DB by `Base.metadata.create_all` in app/database.py:init_db(); this
revision simply records that the live DB is at the baseline so that future
incremental migrations have a known starting point. The live DB is stamped
to this revision rather than running it.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
