"""guest_tokens become one-time join links + device sessions (batch 7, A-01/A-03)

Access off localhost now needs a token (Melvin, 21 Oct 2026). The 13.1
guest_tokens table already holds both kinds: participant_id NULL = curator
device, participant_id set = workshop participant. No role column — that rule
stays in one place (app.models.workshop.is_curator_token).

New columns:
  name          curator device name ("Melvin's phone"); participants use their
                participant row's name
  claimed_at    when the one-time /join/<token> link was used; a claimed link
                can never be used again
  session_hash  sha256 of the cookie secret issued at /join. The link token is
                never a credential itself, so a used link (history, a photo of
                the QR) gives no access.
  last_used_at  last request seen on the session (written at most every 5 min)
expires_at becomes nullable: NULL = never expires (curator devices).

Existing rows keep working as links: unclaimed, no session yet.

Revision ID: 0056_device_tokens
Revises: 0055_refuse_placeholder_markers
"""
from alembic import op
import sqlalchemy as sa

revision = "0056_device_tokens"
down_revision = "0055_refuse_placeholder_markers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("guest_tokens") as batch_op:
        batch_op.add_column(sa.Column("name", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("session_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_used_at", sa.DateTime(), nullable=True))
        batch_op.alter_column("expires_at", existing_type=sa.DateTime(), nullable=True)
    op.create_index("ix_guest_tokens_session_hash", "guest_tokens", ["session_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_guest_tokens_session_hash", table_name="guest_tokens")
    # A curator device has no expiry; give it one so NOT NULL can come back.
    op.execute("UPDATE guest_tokens SET expires_at = datetime('now') WHERE expires_at IS NULL")
    with op.batch_alter_table("guest_tokens") as batch_op:
        batch_op.alter_column("expires_at", existing_type=sa.DateTime(), nullable=False)
        batch_op.drop_column("last_used_at")
        batch_op.drop_column("session_hash")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("name")
