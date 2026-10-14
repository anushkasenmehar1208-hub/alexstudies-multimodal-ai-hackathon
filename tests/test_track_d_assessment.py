"""Adaptive Track D assessment and mastery tests using only the isolated database."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from starlette.applications import Starlette
from starlette.testclient import TestClient

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uni_app import ai_provider  # noqa: E402
from tools.pdf_fixture import build_pdf  # noqa: E402
from uni_app.knowledge_base.api import KnowledgeBaseAPI, add_knowledge_base_routes  # noqa: E402
from uni_app.knowledge_base.models import SourceAsset, SourceBase, TopicMastery  # noqa: E402
from uni_app.knowledge_base.visual_analysis import DeferredVisualAnalyzer  # noqa: E402


OWNER = 1_903_001
OTHER = 1_903_002
CONFIG = ai_provider.ProviderConfig(True, "groq", "test-only", "https://example.invalid", "test", "test")


def _engine():
    url = make_url(os.environ.get("DATABASE_URL", ""))
    if (url.host, url.port, url.database) not in {
        ("127.0.0.1", 55432, "alexstudies_hackathon"),
        ("localhost", 55432, "alexstudies_hackathon"),
    }:
        raise RuntimeError("refusing to run adaptive tests outside the isolated local database")
    return create_engine(url.set(drivername="postgresql+psycopg"), pool_pre_ping=True)


def _pdf() -> bytes:
    text = (
        "Entropy measures microscopic configurations.\n"
        "The first law states that energy is conserved.\n"
        "Pure water boils at 100 degrees Celsius.\n"
        "Temperature describes average particle motion.\n"
        "Heat flows from hotter matter to colder matter."
    )
    return build_pdf([(600, 700, text, None)])


class TrackDAssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()
        SourceBase.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.clean()
        cls.engine.dispose()

    @classmethod
    def clean(cls):
        with cls.engine.begin() as connection:
            connection.execute(delete(TopicMastery).where(TopicMastery.owner_id.in_([OWNER, OTHER])))
            connection.execute(delete(SourceAsset).where(SourceAsset.owner_id.in_([OWNER, OTHER])))

    def setUp(self):
        self.clean()
        app = Starlette()
        self.service = KnowledgeBaseAPI(
            engine=self.engine,
            auth_resolver=lambda token: {"owner": OWNER, "other": OTHER}.get(token, -1),
            provider_config=CONFIG,
            completion=lambda *_args, **_kwargs: "{}",
            visual_analyzer=DeferredVisualAnalyzer(),
        )
        add_knowledge_base_routes(app, self.service)
        self.client = TestClient(app)
        self.headers = {"X-Auth-Token": "owner"}
        response = self.client.post(
            "/api/track-d/sources/pdf",
            headers=self.headers,
            files={"file": ("thermodynamics.pdf", _pdf(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 201, response.text)

    def tearDown(self):
        self.client.close()

    def test_generation_has_three_types_citations_and_deduplication(self):
        first = self.client.post(
            "/api/track-d/assessments",
            headers=self.headers,
            json={"limit": 9, "diagnostic": True},
        )
        self.assertEqual(first.status_code, 201, first.text)
        body = first.json()
        self.assertEqual({item["question_type"] for item in body["questions"]}, {"mcq", "short_answer", "numerical"})
        self.assertTrue(all(item["citation"]["source_unit_id"] > 0 for item in body["questions"]))
        self.assertTrue(all(item["diagnostic"] for item in body["questions"]))

        second = self.client.post(
            "/api/track-d/assessments", headers=self.headers, json={"limit": 9, "diagnostic": True}
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["created_count"], 0)
        self.assertEqual(
            {item["id"] for item in body["questions"]},
            {item["id"] for item in second.json()["questions"]},
        )

    def test_answer_updates_transparent_mastery_and_returns_cited_feedback(self):
        generated = self.service.assessments.generate(owner_id=OWNER, limit=9)
        question = next(item for item in generated.questions if item.question_type == "mcq")
        correct = self.client.post(
            f"/api/track-d/assessments/{question.id}/answer",
            headers=self.headers,
            json={"answer": question.correct_answer},
        )
        self.assertEqual(correct.status_code, 200, correct.text)
        self.assertTrue(correct.json()["is_correct"])
        self.assertEqual(correct.json()["mastery_score"], 100.0)
        wrong = self.client.post(
            f"/api/track-d/assessments/{question.id}/answer",
            headers=self.headers,
            json={"answer": "not the source statement"},
        )
        self.assertEqual(wrong.status_code, 200)
        self.assertEqual(wrong.json()["mastery_score"], 50.0)
        mastery = self.client.get("/api/track-d/mastery", headers=self.headers).json()["mastery"]
        self.assertEqual(mastery[0]["attempt_count"], 2)
        self.assertTrue(mastery[0]["weak"])
        self.assertIn("Review", mastery[0]["recommendation"])
        self.assertGreater(correct.json()["citation"]["source_unit_id"], 0)

    def test_questions_and_answers_are_owner_isolated(self):
        question = self.service.assessments.generate(owner_id=OWNER, limit=1).questions[0]
        self.assertEqual(
            self.client.get("/api/track-d/assessments", headers={"X-Auth-Token": "other"}).json()["questions"],
            [],
        )
        hidden = self.client.post(
            f"/api/track-d/assessments/{question.id}/answer",
            headers={"X-Auth-Token": "other"},
            json={"answer": "anything"},
        )
        self.assertEqual(hidden.status_code, 422)
        self.assertNotIn(str(question.correct_answer), hidden.text)

    def test_unrelated_question_does_not_match_one_generic_word(self):
        self.service.tutor.completion = lambda *_args, **_kwargs: self.fail(
            "provider must not be called for unsupported material"
        )
        response = self.client.post(
            "/api/track-d/tutor",
            headers=self.headers,
            json={"question": "What year did the first humans land on Mars?"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["supported"])
        self.assertEqual(response.json()["citations"], [])


if __name__ == "__main__":
    unittest.main()
