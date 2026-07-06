"""Add medicinal_clinical column to culinary_info

Revision ID: 0030_add_medicinal_clinical_to_culinary_info
Revises:     0029_add_job_queue_heartbeat
Create Date: 2026-06-12

Additive only — adds medicinal_clinical (TEXT, nullable) to culinary_info.
Stores structured JSON tags [{source, label, url?}].
Human-edit only: no AI/draft/generation path touches this field.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0030_add_medicinal_clinical_to_culinary_info"
down_revision = "0029_add_job_queue_heartbeat"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("culinary_info") as batch_op:
        batch_op.add_column(sa.Column("medicinal_clinical", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("culinary_info") as batch_op:
        batch_op.drop_column("medicinal_clinical")
