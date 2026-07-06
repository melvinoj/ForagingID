"""Add top_score, dual_source_agreement, routing_reason to observations

Prerequisite columns for the Phase 10.5 Data Trust & Bulk Correction Dashboard.

  top_score REAL          — cached confidence score of the top candidate
                            (candidates[0].score from species_candidates_json)
  dual_source_agreement INTEGER  — 1 both PlantNet+iNat present, 0 one source, NULL none
  routing_reason TEXT     — most recent processing_log message for this obs

All three are additive (nullable). Populated from existing data in upgrade().
render_as_batch=True is required for SQLite.

Revision ID: 0005_data_trust_columns
Revises: 0004_add_about_content
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_data_trust_columns"
down_revision: Union[str, None] = "0004_add_about_content"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. top_score ────────────────────────────────────────────────────────
    insp = sa.inspect(bind)
    existing_cols = {c["name"] for c in insp.get_columns("observations")}

    if "top_score" not in existing_cols:
        with op.batch_alter_table("observations", recreate="auto") as batch_op:
            batch_op.add_column(sa.Column("top_score", sa.Float(), nullable=True))

    # ── 2. dual_source_agreement ─────────────────────────────────────────────
    # Re-inspect after potential batch recreate
    insp2 = sa.inspect(bind)
    existing_cols2 = {c["name"] for c in insp2.get_columns("observations")}

    if "dual_source_agreement" not in existing_cols2:
        with op.batch_alter_table("observations", recreate="auto") as batch_op:
            batch_op.add_column(sa.Column("dual_source_agreement", sa.Integer(), nullable=True))

    # ── 3. routing_reason ───────────────────────────────────────────────────
    insp3 = sa.inspect(bind)
    existing_cols3 = {c["name"] for c in insp3.get_columns("observations")}

    if "routing_reason" not in existing_cols3:
        with op.batch_alter_table("observations", recreate="auto") as batch_op:
            batch_op.add_column(sa.Column("routing_reason", sa.Text(), nullable=True))

    # ── Backfill top_score from species_candidates_json ──────────────────────
    import json as _json
    rows = bind.execute(
        sa.text(
            "SELECT id, species_candidates_json FROM observations "
            "WHERE species_candidates_json IS NOT NULL AND species_candidates_json != '[]'"
        )
    ).fetchall()

    for obs_id, cands_raw in rows:
        try:
            cands = _json.loads(cands_raw)
            if cands:
                top_score = float(cands[0].get("score", 0.0))
                sources = {c.get("source", "") for c in cands}
                dual = 1 if ("plantnet" in sources and "inaturalist" in sources) else 0
                bind.execute(
                    sa.text(
                        "UPDATE observations SET top_score = :ts, dual_source_agreement = :ds "
                        "WHERE id = :oid"
                    ),
                    {"ts": top_score, "ds": dual, "oid": obs_id},
                )
        except Exception:
            pass

    # Observations with empty candidates → dual_source_agreement = NULL (already NULL)
    # Set dual_source_agreement = 0 for obs that have candidates but only one source
    # (already handled above — dual=0 set when only one source present)

    # ── Backfill routing_reason from processing_logs ─────────────────────────
    bind.execute(sa.text("""
        UPDATE observations
        SET routing_reason = (
            SELECT message
            FROM processing_logs
            WHERE processing_logs.observation_id = observations.id
              AND processing_logs.stage IN ('identify', 'syncthing_prefilter_reject',
                                            'prefilter', 'scan_prefilter')
            ORDER BY processing_logs.id DESC
            LIMIT 1
        )
        WHERE routing_reason IS NULL
    """))


def downgrade() -> None:
    with op.batch_alter_table("observations", recreate="auto") as batch_op:
        for col in ("routing_reason", "dual_source_agreement", "top_score"):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
