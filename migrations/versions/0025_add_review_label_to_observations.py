"""Add review_label to observations

Revision ID: 0025_add_review_label_to_observations
Revises:     0024_add_foraging_sessions
Create Date: 2026-06-05

Additive only — adds nullable VARCHAR(32) column, then backfills
existing needs_review rows from available data signals.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0025_add_review_label_to_observations"
down_revision = "0024_add_foraging_sessions"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add column (idempotent guard)
    cols = {row[1] for row in bind.execute(sa.text("PRAGMA table_info(observations)"))}
    if "review_label" not in cols:
        op.add_column("observations", sa.Column("review_label", sa.String(32), nullable=True))

    # 2. Backfill existing needs_review rows — first match wins
    # Priority: non_plant > low_confidence > no_gps > failed_id > manual_review

    # non_plant: obs_category is fungi/landscape, OR routing_reason mentions kingdom
    bind.execute(sa.text("""
        UPDATE observations
        SET review_label = 'non_plant'
        WHERE review_status = 'needs_review'
          AND review_label IS NULL
          AND (
            obs_category IN ('fungi', 'landscape')
            OR lower(routing_reason) LIKE '%kingdom%'
            OR lower(routing_reason) LIKE '%not_plant%'
            OR lower(routing_reason) LIKE '%person_animal%'
          )
    """))

    # low_confidence: top_score below 0.7
    bind.execute(sa.text("""
        UPDATE observations
        SET review_label = 'low_confidence'
        WHERE review_status = 'needs_review'
          AND review_label IS NULL
          AND top_score IS NOT NULL
          AND top_score < 0.7
    """))

    # no_gps: missing coordinates
    bind.execute(sa.text("""
        UPDATE observations
        SET review_label = 'no_gps'
        WHERE review_status = 'needs_review'
          AND review_label IS NULL
          AND (latitude IS NULL OR longitude IS NULL)
    """))

    # failed_id: identification_status = failed_identification or below_threshold with no candidates
    bind.execute(sa.text("""
        UPDATE observations
        SET review_label = 'failed_id'
        WHERE review_status = 'needs_review'
          AND review_label IS NULL
          AND (
            identification_status = 'failed_identification'
            OR (identification_status = 'below_threshold'
                AND (species_candidates_json IS NULL OR species_candidates_json = '[]'))
          )
    """))

    # manual_review: everything remaining in needs_review with no label
    bind.execute(sa.text("""
        UPDATE observations
        SET review_label = 'manual_review'
        WHERE review_status = 'needs_review'
          AND review_label IS NULL
    """))


def downgrade() -> None:
    op.drop_column("observations", "review_label")
