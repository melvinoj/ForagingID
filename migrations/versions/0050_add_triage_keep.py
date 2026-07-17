"""add triage_keep, triage_keep_at, never_reject to observations

Persists human triage decisions that previously existed only in a session
transcript. Three columns, all nullable, all additive — no existing row or
read path is affected.

triage_keep    Three-state, deliberately NOT a default-0 boolean:
                 NULL = untriaged (the 12,240 rows nobody has looked at)
                 1    = human keeper
                 0    = explicit human discard
               A default-0 boolean would erase the distinction between "not yet
               triaged" and "explicitly discarded", which is exactly the
               information a delete-by-omission pass depends on.

triage_keep_at When the call was made. Separate from reviewed_at, which belongs
               to the review pipeline, not to triage.

never_reject   Data-protection flag, orthogonal to triage_keep. "Keep this
               photo" and "this photo has no other copy on disk" are different
               assertions: clearing a triage decision must not silently drop a
               data-protection guarantee. Enforced inside
               delete_observation_file() so the protection lives at the
               destructive call site rather than in prose.

Revision ID: 0050_add_triage_keep
Revises: 0049_add_species_orphaned_at
"""
from alembic import op
import sqlalchemy as sa

revision = "0050_add_triage_keep"
down_revision = "0049_add_species_orphaned_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("observations", sa.Column("triage_keep", sa.Boolean(), nullable=True))
    op.add_column("observations", sa.Column("triage_keep_at", sa.DateTime(), nullable=True))
    op.add_column("observations", sa.Column("never_reject", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("observations", "never_reject")
    op.drop_column("observations", "triage_keep_at")
    op.drop_column("observations", "triage_keep")
