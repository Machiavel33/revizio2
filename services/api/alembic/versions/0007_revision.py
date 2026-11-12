"""tags, manual sheets, exam folders, quizzes

Revision ID: 0007_revision
Revises: 0006_admin_full
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_revision"
down_revision: str | None = "0006_admin_full"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Course.tags
    op.add_column(
        "courses",
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
    )

    # StudySheet : fiche manuelle (course_id nullable + champs)
    op.alter_column("study_sheets", "course_id", existing_type=postgresql.UUID(), nullable=True)
    op.add_column(
        "study_sheets",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "study_sheets", sa.Column("title", sa.String(length=255), nullable=False, server_default="")
    )
    op.add_column("study_sheets", sa.Column("subject", sa.String(length=120), nullable=True))
    op.add_column(
        "study_sheets",
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "study_sheets",
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_study_sheets_user", "study_sheets", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_study_sheets_user_id", "study_sheets", ["user_id"])

    # Exam folders
    op.create_table(
        "exam_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exam_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_exam_folders_user_id", "exam_folders", ["user_id"])

    op.create_table(
        "exam_folder_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_folders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_sheet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_sheets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_exam_folder_items_folder_id", "exam_folder_items", ["folder_id"])
    op.create_index("ix_exam_folder_items_sheet_id", "exam_folder_items", ["study_sheet_id"])

    # Quizzes
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exam_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Quiz"),
        sa.Column("model", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quiz_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("choices", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("correct_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])


def downgrade() -> None:
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")
    op.drop_table("exam_folder_items")
    op.drop_table("exam_folders")
    op.drop_index("ix_study_sheets_user_id", "study_sheets")
    op.drop_constraint("fk_study_sheets_user", "study_sheets", type_="foreignkey")
    op.drop_column("study_sheets", "is_manual")
    op.drop_column("study_sheets", "tags")
    op.drop_column("study_sheets", "subject")
    op.drop_column("study_sheets", "title")
    op.drop_column("study_sheets", "user_id")
    op.alter_column("study_sheets", "course_id", existing_type=postgresql.UUID(), nullable=False)
    op.drop_column("courses", "tags")
