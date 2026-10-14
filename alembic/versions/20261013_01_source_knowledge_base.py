"""Create the Track D Phase 1 source knowledge-base tables.

Revision ID: 20261013_01
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extraction_status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_type IN ('youtube', 'pdf', 'pptx')", name="ck_source_asset_type"),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'complete', 'partial', 'failed')",
            name="ck_source_asset_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_source_asset_id_owner"),
        sa.UniqueConstraint("owner_id", "source_type", "content_hash", name="uq_source_asset_owner_hash"),
    )
    op.create_index("ix_source_assets_owner_id", "source_assets", ["owner_id"], unique=False)
    op.create_index("ix_source_asset_owner_created", "source_assets", ["owner_id", "created_at"], unique=False)

    op.create_table(
        "source_units",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_locator", sa.JSON(), nullable=False),
        sa.Column("extraction_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_type IN ('youtube', 'pdf', 'pptx')", name="ck_source_unit_type"),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'complete', 'partial', 'failed')",
            name="ck_source_unit_status",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "owner_id"],
            ["source_assets.id", "source_assets.owner_id"],
            name="fk_source_unit_asset_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "unit_index", name="uq_source_unit_asset_index"),
        sa.UniqueConstraint("id", "owner_id", name="uq_source_unit_id_owner"),
        sa.UniqueConstraint("id", "asset_id", "owner_id", name="uq_source_unit_id_asset_owner"),
    )
    op.create_index("ix_source_unit_owner_asset", "source_units", ["owner_id", "asset_id"], unique=False)
    op.create_index("ix_source_unit_content_hash", "source_units", ["content_hash"], unique=False)

    op.create_table(
        "source_visuals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("source_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("image_index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("image_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("source_locator", sa.JSON(), nullable=False),
        sa.Column("extraction_status", sa.String(length=16), nullable=False),
        sa.Column("analysis_status", sa.String(length=20), nullable=False),
        sa.Column("analyzer_name", sa.String(length=80), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("visual_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "extraction_status IN ('pending', 'complete', 'partial', 'failed')",
            name="ck_source_visual_status",
        ),
        sa.CheckConstraint(
            "analysis_status IN ('not_requested', 'complete', 'failed')",
            name="ck_source_visual_analysis_status",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "owner_id"],
            ["source_assets.id", "source_assets.owner_id"],
            name="fk_source_visual_asset_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_unit_id", "asset_id", "owner_id"],
            ["source_units.id", "source_units.asset_id", "source_units.owner_id"],
            name="fk_source_visual_unit_asset_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "unit_index", "image_index", name="uq_source_visual_location"),
    )
    op.create_index("ix_source_visual_owner_asset", "source_visuals", ["owner_id", "asset_id"], unique=False)

    op.create_table(
        "topics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_topic_id_owner"),
        sa.UniqueConstraint("owner_id", "normalized_name", name="uq_topic_owner_name"),
    )
    op.create_index("ix_topic_owner", "topics", ["owner_id"], unique=False)

    op.create_table(
        "topic_prerequisites",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("prerequisite_topic_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("topic_id <> prerequisite_topic_id", name="ck_topic_not_own_prerequisite"),
        sa.ForeignKeyConstraint(
            ["prerequisite_topic_id", "owner_id"],
            ["topics.id", "topics.owner_id"],
            name="fk_topic_prerequisite_parent_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id", "owner_id"],
            ["topics.id", "topics.owner_id"],
            name="fk_topic_prerequisite_topic_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "prerequisite_topic_id", name="uq_topic_prerequisite"),
    )

    op.create_table(
        "source_unit_topics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("source_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("relevance", sa.Float(), nullable=False),
        sa.Column("assignment_source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("relevance >= 0 AND relevance <= 1", name="ck_source_unit_topic_relevance"),
        sa.ForeignKeyConstraint(
            ["source_unit_id", "owner_id"],
            ["source_units.id", "source_units.owner_id"],
            name="fk_source_unit_topic_unit_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id", "owner_id"],
            ["topics.id", "topics.owner_id"],
            name="fk_source_unit_topic_topic_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_unit_id", "topic_id", name="uq_source_unit_topic"),
    )


def downgrade() -> None:
    op.drop_table("source_unit_topics")
    op.drop_table("topic_prerequisites")
    op.drop_index("ix_topic_owner", table_name="topics")
    op.drop_table("topics")
    op.drop_index("ix_source_visual_owner_asset", table_name="source_visuals")
    op.drop_table("source_visuals")
    op.drop_index("ix_source_unit_content_hash", table_name="source_units")
    op.drop_index("ix_source_unit_owner_asset", table_name="source_units")
    op.drop_table("source_units")
    op.drop_index("ix_source_asset_owner_created", table_name="source_assets")
    op.drop_index("ix_source_assets_owner_id", table_name="source_assets")
    op.drop_table("source_assets")
