"""invoices (facturation refacturation clé plateforme)

Revision ID: 0009_invoices
Revises: 0008_user_names
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0009_invoices"
down_revision: str | None = "0008_user_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vat", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lines", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_session_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("number", name="uq_invoice_number"),
    )
    op.create_index("ix_invoices_number", "invoices", ["number"])
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])
    op.create_index("ix_invoices_period", "invoices", ["period"])
    op.create_index("ix_invoices_status", "invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_period", table_name="invoices")
    op.drop_index("ix_invoices_user_id", table_name="invoices")
    op.drop_index("ix_invoices_number", table_name="invoices")
    op.drop_table("invoices")
