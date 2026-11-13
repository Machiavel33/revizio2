"""course domain (encadrement IA explicite)

Revision ID: 0010_course_domain
Revises: 0009_invoices
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_course_domain"
down_revision: str | None = "0009_invoices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("domain", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("courses", "domain")
