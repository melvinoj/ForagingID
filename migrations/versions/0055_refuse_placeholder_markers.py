"""refuse placeholder markers in warning fields and field history (audit E-14)

One-off SQL in June 2026 (21, 22 and 24 Jun; no code in git wrote it) stored 11
culinary_info_history rows whose new_value is a stand-in, not content — "(set)"
and "(human-authored preparation_warnings)". A human-lock row that holds a
marker locks the field without recording what was locked, and the curator-
authored test (latest human row == current text) then fails, so real curator
text reads as unreviewed.

These triggers refuse a new marker at the database, whatever the writer — the
ORM, a script, or a one-off sqlite3 session:
  culinary_info_history  INSERT, and UPDATE of new_value (any field)
  culinary_info          INSERT, and UPDATE of preparation_warnings /
                         look_alike_warnings
Existing rows are untouched (the clean-up is a separate, curator-confirmed step).

"Marker" = the whole value is one parenthesised phrase of at most 80 characters
— app.models.species.is_placeholder_marker(). _marker_sql() below is a frozen
copy of placeholder_marker_sql() (a migration must not change when app code
does); tests/test_batch6_warnings.py keeps the two equal.

Revision ID: 0055_refuse_placeholder_markers
Revises: 0054_experience_publications
"""
from alembic import op

revision = "0055_refuse_placeholder_markers"
down_revision = "0054_experience_publications"
branch_labels = None
depends_on = None

_MSG = "placeholder marker refused (audit E-14): store the real text, not a stand-in"
_WS = "' ' || char(9) || char(10) || char(13)"


def _marker_sql(col: str) -> str:
    t = f"trim({col}, {_WS})"
    return (f"(length({t}) BETWEEN 2 AND 80 AND substr({t}, 1, 1) = '(' "
            f"AND substr({t}, -1, 1) = ')' AND instr(substr({t}, 2, length({t}) - 2), ')') = 0)")


_HIST = _marker_sql("NEW.new_value")
_CI = f"{_marker_sql('NEW.preparation_warnings')} OR {_marker_sql('NEW.look_alike_warnings')}"

TRIGGERS = {
    "trg_cih_no_marker_insert":
        f"CREATE TRIGGER trg_cih_no_marker_insert BEFORE INSERT ON culinary_info_history "
        f"WHEN {_HIST} BEGIN SELECT RAISE(ABORT, '{_MSG}'); END",
    "trg_cih_no_marker_update":
        f"CREATE TRIGGER trg_cih_no_marker_update BEFORE UPDATE OF new_value ON culinary_info_history "
        f"WHEN {_HIST} BEGIN SELECT RAISE(ABORT, '{_MSG}'); END",
    "trg_ci_no_marker_insert":
        f"CREATE TRIGGER trg_ci_no_marker_insert BEFORE INSERT ON culinary_info "
        f"WHEN {_CI} BEGIN SELECT RAISE(ABORT, '{_MSG}'); END",
    "trg_ci_no_marker_update":
        f"CREATE TRIGGER trg_ci_no_marker_update BEFORE UPDATE OF preparation_warnings, look_alike_warnings "
        f"ON culinary_info WHEN {_CI} BEGIN SELECT RAISE(ABORT, '{_MSG}'); END",
}


def upgrade() -> None:
    for sql in TRIGGERS.values():
        op.execute(sql)


def downgrade() -> None:
    for name in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
