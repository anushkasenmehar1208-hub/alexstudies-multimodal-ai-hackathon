"""SQLAlchemy models for location-preserving learning sources.

These tables deliberately do not depend on the existing Reflex model metadata.
They are installed through Alembic so Phase 1 can be tested without importing or
initializing the full application.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


SOURCE_TYPES = ("youtube", "pdf", "pptx")
EXTRACTION_STATUSES = ("pending", "complete", "partial", "failed")
ANALYSIS_STATUSES = ("not_requested", "complete", "unavailable", "failed")


class SourceBase(DeclarativeBase):
    """Metadata root for the isolated knowledge-base schema."""


class SourceAsset(SourceBase):
    __tablename__ = "source_assets"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_type", "content_hash", name="uq_source_asset_owner_hash"),
        UniqueConstraint("id", "owner_id", name="uq_source_asset_id_owner"),
        CheckConstraint(
            "source_type IN ('youtube', 'pdf', 'pptx')",
            name="ck_source_asset_type",
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'complete', 'partial', 'failed')",
            name="ck_source_asset_status",
        ),
        Index("ix_source_asset_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    original_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourceUnit(SourceBase):
    __tablename__ = "source_units"
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "owner_id"],
            ["source_assets.id", "source_assets.owner_id"],
            ondelete="CASCADE",
            name="fk_source_unit_asset_owner",
        ),
        UniqueConstraint("asset_id", "unit_index", name="uq_source_unit_asset_index"),
        UniqueConstraint("id", "owner_id", name="uq_source_unit_id_owner"),
        UniqueConstraint("id", "asset_id", "owner_id", name="uq_source_unit_id_asset_owner"),
        CheckConstraint(
            "source_type IN ('youtube', 'pdf', 'pptx')",
            name="ck_source_unit_type",
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'complete', 'partial', 'failed')",
            name="ck_source_unit_status",
        ),
        Index("ix_source_unit_owner_asset", "owner_id", "asset_id"),
        Index("ix_source_unit_content_hash", "content_hash"),
        Index(
            "ix_source_units_search_vector",
            text("to_tsvector('english'::regconfig, extracted_text)"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="complete")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceVisual(SourceBase):
    __tablename__ = "source_visuals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "owner_id"],
            ["source_assets.id", "source_assets.owner_id"],
            ondelete="CASCADE",
            name="fk_source_visual_asset_owner",
        ),
        ForeignKeyConstraint(
            ["source_unit_id", "asset_id", "owner_id"],
            ["source_units.id", "source_units.asset_id", "source_units.owner_id"],
            ondelete="CASCADE",
            name="fk_source_visual_unit_asset_owner",
        ),
        UniqueConstraint("asset_id", "unit_index", "image_index", name="uq_source_visual_location"),
        CheckConstraint(
            "extraction_status IN ('pending', 'complete', 'partial', 'failed')",
            name="ck_source_visual_status",
        ),
        CheckConstraint(
            "analysis_status IN ('not_requested', 'complete', 'unavailable', 'failed')",
            name="ck_source_visual_analysis_status",
        ),
        Index("ix_source_visual_owner_asset", "owner_id", "asset_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_unit_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    image_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    image_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="complete")
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_requested")
    analyzer_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visual_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Topic(SourceBase):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("owner_id", "normalized_name", name="uq_topic_owner_name"),
        UniqueConstraint("id", "owner_id", name="uq_topic_id_owner"),
        Index("ix_topic_owner", "owner_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TopicPrerequisite(SourceBase):
    __tablename__ = "topic_prerequisites"
    __table_args__ = (
        ForeignKeyConstraint(
            ["topic_id", "owner_id"],
            ["topics.id", "topics.owner_id"],
            ondelete="CASCADE",
            name="fk_topic_prerequisite_topic_owner",
        ),
        ForeignKeyConstraint(
            ["prerequisite_topic_id", "owner_id"],
            ["topics.id", "topics.owner_id"],
            ondelete="CASCADE",
            name="fk_topic_prerequisite_parent_owner",
        ),
        UniqueConstraint("topic_id", "prerequisite_topic_id", name="uq_topic_prerequisite"),
        CheckConstraint("topic_id <> prerequisite_topic_id", name="ck_topic_not_own_prerequisite"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prerequisite_topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceUnitTopic(SourceBase):
    __tablename__ = "source_unit_topics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_unit_id", "owner_id"],
            ["source_units.id", "source_units.owner_id"],
            ondelete="CASCADE",
            name="fk_source_unit_topic_unit_owner",
        ),
        ForeignKeyConstraint(
            ["topic_id", "owner_id"],
            ["topics.id", "topics.owner_id"],
            ondelete="CASCADE",
            name="fk_source_unit_topic_topic_owner",
        ),
        UniqueConstraint("source_unit_id", "topic_id", name="uq_source_unit_topic"),
        CheckConstraint("relevance >= 0 AND relevance <= 1", name="ck_source_unit_topic_relevance"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_unit_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    relevance: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    assignment_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssessmentQuestion(SourceBase):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_unit_id", "asset_id", "owner_id"],
            ["source_units.id", "source_units.asset_id", "source_units.owner_id"],
            ondelete="CASCADE",
            name="fk_assessment_question_unit_owner",
        ),
        UniqueConstraint("id", "owner_id", name="uq_assessment_question_id_owner"),
        UniqueConstraint("owner_id", "fingerprint", name="uq_assessment_question_owner_fingerprint"),
        CheckConstraint(
            "question_type IN ('mcq', 'short_answer', 'numerical')",
            name="ck_assessment_question_type",
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_assessment_question_difficulty",
        ),
        Index("ix_assessment_question_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_unit_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    topic_tag: Mapped[str] = mapped_column(String(120), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    citation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    diagnostic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssessmentAttempt(SourceBase):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id", "owner_id"],
            ["assessment_questions.id", "assessment_questions.owner_id"],
            ondelete="CASCADE",
            name="fk_assessment_attempt_question_owner",
        ),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_assessment_attempt_score"),
        Index("ix_assessment_attempt_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    question_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submitted_answer: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TopicMastery(SourceBase):
    __tablename__ = "topic_mastery"
    __table_args__ = (
        UniqueConstraint("owner_id", "topic_tag", name="uq_topic_mastery_owner_topic"),
        CheckConstraint("mastery_score >= 0 AND mastery_score <= 100", name="ck_topic_mastery_score"),
        CheckConstraint("attempt_count >= 0", name="ck_topic_mastery_attempts"),
        CheckConstraint("correct_count >= 0", name="ck_topic_mastery_correct"),
        Index("ix_topic_mastery_owner_score", "owner_id", "mastery_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_tag: Mapped[str] = mapped_column(String(120), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
