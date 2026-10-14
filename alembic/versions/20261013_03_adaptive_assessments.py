"""Add deterministic assessments, attempts and topic mastery.

Revision ID: 20261013_03
Revises: 20261013_02
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_03"
down_revision: str | None = "20261013_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("source_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("question_type", sa.String(length=20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("answer_metadata", sa.JSON(), nullable=False),
        sa.Column("topic_tag", sa.String(length=120), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("citation", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("diagnostic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "question_type IN ('mcq', 'short_answer', 'numerical')",
            name="ck_assessment_question_type",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_assessment_question_difficulty",
        ),
        sa.ForeignKeyConstraint(
            ["source_unit_id", "asset_id", "owner_id"],
            ["source_units.id", "source_units.asset_id", "source_units.owner_id"],
            name="fk_assessment_question_unit_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_assessment_question_id_owner"),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_assessment_question_owner_fingerprint"),
    )
    op.create_index(
        "ix_assessment_question_owner_created",
        "assessment_questions",
        ["owner_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("submitted_answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_assessment_attempt_score"),
        sa.ForeignKeyConstraint(
            ["question_id", "owner_id"],
            ["assessment_questions.id", "assessment_questions.owner_id"],
            name="fk_assessment_attempt_question_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_attempt_owner_created",
        "assessment_attempts",
        ["owner_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "topic_mastery",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_tag", sa.String(length=120), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("mastery_score >= 0 AND mastery_score <= 100", name="ck_topic_mastery_score"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_topic_mastery_attempts"),
        sa.CheckConstraint("correct_count >= 0", name="ck_topic_mastery_correct"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "topic_tag", name="uq_topic_mastery_owner_topic"),
    )
    op.create_index(
        "ix_topic_mastery_owner_score",
        "topic_mastery",
        ["owner_id", "mastery_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_topic_mastery_owner_score", table_name="topic_mastery")
    op.drop_table("topic_mastery")
    op.drop_index("ix_assessment_attempt_owner_created", table_name="assessment_attempts")
    op.drop_table("assessment_attempts")
    op.drop_index("ix_assessment_question_owner_created", table_name="assessment_questions")
    op.drop_table("assessment_questions")
