"""platform keys + user key_mode

Revision ID: 0004_platform_keys
Revises: 0003_totp
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_platform_keys"
down_revision: str | None = "0003_totp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("key_mode", sa.String(length=20), nullable=False, server_default="byok"),
    )
    op.create_table(
        "platform_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_hint", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", name="uq_platform_provider"),
    )


def downgrade() -> None:
    op.drop_table("platform_keys")
    op.drop_column("users", "key_mode")
