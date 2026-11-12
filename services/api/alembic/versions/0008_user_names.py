"""user first_name / last_name

Revision ID: 0008_user_names
Revises: 0007_revision
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_names"
down_revision: str | None = "0007_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("first_name", sa.String(length=80), nullable=False, server_default="")
    )
    op.add_column(
        "users", sa.Column("last_name", sa.String(length=80), nullable=False, server_default="")
    )


def downgrade() -> None:
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
