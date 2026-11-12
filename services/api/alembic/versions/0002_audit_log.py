"""audit log immutable chain

Revision ID: 0002_audit_log
Revises: 0001_initial
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_audit_log"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Séquence atomique pour le seq (évite les collisions sous concurrence)
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit_logs_seq")
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("prev_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_seq", "audit_logs", ["seq"], unique=True)
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_entry_hash", "audit_logs", ["entry_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.execute("DROP SEQUENCE IF EXISTS audit_logs_seq")
