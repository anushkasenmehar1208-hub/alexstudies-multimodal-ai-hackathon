"""Fresh-database bootstrap checks restricted to the disposable Track D database."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).parents[1]
USERNAME = "bootstrap-preservation-test"


def _database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    url = make_url(raw)
    if (url.host, url.port, url.database) not in {
        ("127.0.0.1", 55432, "alexstudies_hackathon"),
        ("localhost", 55432, "alexstudies_hackathon"),
    }:
        raise RuntimeError("refusing to test database bootstrap outside the disposable local database")
    return raw


class DatabaseBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = _database_url()
        cls.engine = create_engine(
            make_url(cls.database_url).set(drivername="postgresql+psycopg"),
            pool_pre_ping=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._clean()
        cls.engine.dispose()

    @classmethod
    def _clean(cls) -> None:
        with cls.engine.begin() as connection:
            user_id = connection.execute(
                text("SELECT id FROM localuser WHERE username=:username"),
                {"username": USERNAME},
            ).scalar_one_or_none()
            if user_id is None:
                return
            for table in ("localauthsession", "usermemory", "userprofile"):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE user_id=:user_id"),
                    {"user_id": user_id},
                )
            connection.execute(
                text("DELETE FROM localuser WHERE id=:user_id"),
                {"user_id": user_id},
            )

    def setUp(self) -> None:
        self._clean()

    def test_required_auth_profile_and_track_d_schema_exists_at_head(self) -> None:
        schema = inspect(self.engine)
        tables = set(schema.get_table_names())
        required = {
            "alembic_version",
            "localuser",
            "localauthsession",
            "userprofile",
            "usermemory",
            "auththrottle",
            "source_assets",
            "source_units",
            "source_visuals",
            "assessment_questions",
            "assessment_attempts",
            "topic_mastery",
        }
        self.assertTrue(required.issubset(tables), sorted(required - tables))
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(),
                "20261013_03",
            )

    def test_rerun_is_idempotent_and_preserves_authentication_data(self) -> None:
        with self.engine.begin() as connection:
            user_id = connection.execute(
                text(
                    "INSERT INTO localuser (username, password_hash, enabled) "
                    "VALUES (:username, :password_hash, true) RETURNING id"
                ),
                {"username": USERNAME, "password_hash": b"test-only-hash"},
            ).scalar_one()
            connection.execute(
                text("INSERT INTO userprofile (user_id, email) VALUES (:user_id, :email)"),
                {"user_id": user_id, "email": "bootstrap-test@example.invalid"},
            )
            connection.execute(
                text(
                    "INSERT INTO usermemory "
                    "(user_id, degree, pathway, is_started, selected_year, selected_semester) "
                    "VALUES (:user_id, 'Physical Science', 'AMAT / PHYS / PMAT', true, 'Year 1', 'Semester 1')"
                ),
                {"user_id": user_id},
            )
            connection.execute(
                text("INSERT INTO localauthsession (user_id, session_id) VALUES (:user_id, :session_id)"),
                {"user_id": user_id, "session_id": "bootstrap-preservation-session"},
            )

        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": self.database_url},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT u.enabled, p.email, p.is_onboarded, m.degree, m.active_subject, s.session_id "
                    "FROM localuser u "
                    "JOIN userprofile p ON p.user_id=u.id "
                    "JOIN usermemory m ON m.user_id=u.id "
                    "JOIN localauthsession s ON s.user_id=u.id "
                    "WHERE u.username=:username"
                ),
                {"username": USERNAME},
            ).one()
        self.assertEqual(
            tuple(row),
            (
                True,
                "bootstrap-test@example.invalid",
                False,
                "Physical Science",
                "",
                "bootstrap-preservation-session",
            ),
        )


if __name__ == "__main__":
    unittest.main()
