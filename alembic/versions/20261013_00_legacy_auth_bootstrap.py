"""Create the legacy authentication and profile tables required by Track D.

Revision ID: 20261013_00
Revises:
Create Date: 2026-10-14

The original Reflex application created these tables as an import-time side
effect.  This baseline makes fresh database creation deterministic while
leaving an already-initialized database and its rows untouched.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_00"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "localuser" not in existing:
        op.create_table(
            "localuser",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.LargeBinary(), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username", name="uq_localuser_username"),
        )
        op.create_index("ix_localuser_username", "localuser", ["username"], unique=True)

    if "localauthsession" not in existing:
        op.create_table(
            "localauthsession",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=255), nullable=False),
            sa.Column(
                "expiration",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", name="uq_localauthsession_session_id"),
        )
        op.create_index("ix_localauthsession_user_id", "localauthsession", ["user_id"])
        op.create_index(
            "ix_localauthsession_session_id",
            "localauthsession",
            ["session_id"],
            unique=True,
        )

    if "userprofile" not in existing:
        op.create_table(
            "userprofile",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("is_onboarded", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("email", sa.String(), server_default="", nullable=False),
            sa.Column("unique_id", sa.String(), server_default="", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("is_pro", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("is_premium_1", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("is_premium_2", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("plan_tier", sa.String(length=24), server_default="free", nullable=False),
            sa.Column("model_usage_json", sa.String(), server_default="{}", nullable=False),
            sa.Column("premium_activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("daily_message_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("last_message_date", sa.Date(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_userprofile_user_id"),
        )
        op.create_index("ix_userprofile_user_id", "userprofile", ["user_id"], unique=True)

    if "usermemory" not in existing:
        op.create_table(
            "usermemory",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("step", sa.Integer(), server_default="0", nullable=False),
            sa.Column("name", sa.String(), server_default="", nullable=False),
            sa.Column("degree", sa.String(), server_default="", nullable=False),
            sa.Column("pathway", sa.String(), server_default="", nullable=False),
            sa.Column("active_subject", sa.String(), server_default="", nullable=False),
            sa.Column("is_started", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("selected_year", sa.String(), server_default="", nullable=False),
            sa.Column("selected_semester", sa.String(), server_default="", nullable=False),
            sa.Column("summary", sa.String(), server_default="", nullable=False),
            sa.Column("other_degree_text", sa.String(), server_default="", nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_usermemory_user_id"),
        )
        op.create_index("ix_usermemory_user_id", "usermemory", ["user_id"], unique=True)

    if "auththrottle" not in existing:
        op.create_table(
            "auththrottle",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", name="uq_auththrottle_key"),
        )
        op.create_index("ix_auththrottle_key", "auththrottle", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_auththrottle_key", table_name="auththrottle")
    op.drop_table("auththrottle")
    op.drop_index("ix_usermemory_user_id", table_name="usermemory")
    op.drop_table("usermemory")
    op.drop_index("ix_userprofile_user_id", table_name="userprofile")
    op.drop_table("userprofile")
    op.drop_index("ix_localauthsession_session_id", table_name="localauthsession")
    op.drop_index("ix_localauthsession_user_id", table_name="localauthsession")
    op.drop_table("localauthsession")
    op.drop_index("ix_localuser_username", table_name="localuser")
    op.drop_table("localuser")
