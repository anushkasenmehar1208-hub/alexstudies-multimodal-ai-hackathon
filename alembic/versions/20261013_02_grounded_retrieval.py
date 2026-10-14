"""Add Track D full-text retrieval and explicit visual unavailability.

Revision ID: 20261013_02
Revises: 20261013_01
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20261013_02"
down_revision: str | None = "20261013_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_source_visual_analysis_status", "source_visuals", type_="check")
    op.create_check_constraint(
        "ck_source_visual_analysis_status",
        "source_visuals",
        "analysis_status IN ('not_requested', 'complete', 'unavailable', 'failed')",
    )
    op.execute(
        "CREATE INDEX ix_source_units_search_vector ON source_units "
        "USING gin (to_tsvector('english'::regconfig, extracted_text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_source_units_search_vector")
    op.execute(
        "UPDATE source_visuals SET analysis_status = 'failed' "
        "WHERE analysis_status = 'unavailable'"
    )
    op.drop_constraint("ck_source_visual_analysis_status", "source_visuals", type_="check")
    op.create_check_constraint(
        "ck_source_visual_analysis_status",
        "source_visuals",
        "analysis_status IN ('not_requested', 'complete', 'failed')",
    )
