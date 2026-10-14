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

    def test_diagnostic_drives_cited_adaptive_cycle_and_difficulty(self):
        generated = self.service.assessments.generate(owner_id=OWNER, limit=9, diagnostic=True)
        diagnostic = next(item for item in generated.questions if item.question_type == "mcq")
        wrong = self.client.post(
            f"/api/track-d/assessments/{diagnostic.id}/answer",
            headers=self.headers,
            json={"answer": "not the source statement"},
        )
        self.assertEqual(wrong.status_code, 200, wrong.text)
        self.assertFalse(wrong.json()["is_correct"])
        self.assertIn("Source-backed explanation", wrong.json()["feedback"])

        easy = self.client.post(
            "/api/track-d/assessments/adaptive", headers=self.headers, json={}
        )
        self.assertEqual(easy.status_code, 200, easy.text)
        easy_body = easy.json()
        self.assertTrue(easy_body["weak"])
        self.assertEqual(easy_body["mastery_score"], 0.0)
        self.assertEqual(easy_body["difficulty"], "easy")
        self.assertTrue(easy_body["question"]["adaptive"])
        self.assertEqual(easy_body["question"]["topic_tag"], diagnostic.topic_tag)
        self.assertGreater(easy_body["question"]["citation"]["source_unit_id"], 0)

        easy_question = next(
            item for item in self.service.assessments.list_questions(owner_id=OWNER)
            if item.id == easy_body["question"]["id"]
        )
        first_correct = self.client.post(
            f"/api/track-d/assessments/{easy_question.id}/answer",
            headers=self.headers,
            json={"answer": easy_question.correct_answer},
        )
        self.assertEqual(first_correct.status_code, 200, first_correct.text)
        self.assertEqual(first_correct.json()["mastery_score"], 50.0)

        medium = self.client.post(
            "/api/track-d/assessments/adaptive", headers=self.headers, json={}
        )
        self.assertEqual(medium.status_code, 200, medium.text)
        self.assertEqual(medium.json()["difficulty"], "medium")
        medium_question = next(
            item for item in self.service.assessments.list_questions(owner_id=OWNER)
            if item.id == medium.json()["question"]["id"]
        )
        for expected_mastery in (66.67, 75.0):
            response = self.client.post(
                f"/api/track-d/assessments/{medium_question.id}/answer",
                headers=self.headers,
                json={"answer": medium_question.correct_answer},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertAlmostEqual(response.json()["mastery_score"], expected_mastery, places=2)

        hard = self.client.post(
            "/api/track-d/assessments/adaptive", headers=self.headers, json={}
        )
        self.assertEqual(hard.status_code, 200, hard.text)
        self.assertFalse(hard.json()["weak"])
        self.assertEqual(hard.json()["difficulty"], "hard")
        self.assertIn("at or above 70%", hard.json()["rationale"])

    def test_adaptive_follow_up_requires_owner_mastery_and_never_leaks(self):
        generated = self.service.assessments.generate(owner_id=OWNER, limit=1, diagnostic=True)
        question = generated.questions[0]
        self.client.post(
            f"/api/track-d/assessments/{question.id}/answer",
            headers=self.headers,
            json={"answer": "wrong"},
        )
        own = self.client.post(
            "/api/track-d/assessments/adaptive", headers=self.headers, json={}
        )
        self.assertEqual(own.status_code, 200, own.text)
        other = self.client.post(
            "/api/track-d/assessments/adaptive",
            headers={"X-Auth-Token": "other"},
            json={},
        )
        self.assertEqual(other.status_code, 422)
        self.assertNotIn(own.json()["selected_topic"], other.text)
        self.assertEqual(
            self.client.post("/api/track-d/assessments/adaptive", json={}).status_code,
            401,
        )

    def test_adaptive_follow_up_selects_lowest_mastery_across_topics(self):
        biology = build_pdf([(
            600,
            700,
            (
                "Mitosis produces two genetically similar daughter cells.\n"
                "Chromosomes align at the cell equator during metaphase.\n"
                "Spindle fibres separate sister chromatids during anaphase.\n"
                "Cytokinesis divides the cytoplasm after nuclear division."
            ),
            None,
        )])
        uploaded = self.client.post(
            "/api/track-d/sources/pdf",
            headers=self.headers,
            files={"file": ("mitosis.pdf", biology, "application/pdf")},
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)

        generated = self.service.assessments.generate(owner_id=OWNER, limit=15, diagnostic=True)
        mcqs = {}
        for item in generated.questions:
            if item.question_type == "mcq":
                mcqs.setdefault(item.topic_tag, item)
        self.assertGreaterEqual(len(mcqs), 2)
        weak_topic, strong_topic = list(mcqs)[:2]

        weak = mcqs[weak_topic]
        strong = mcqs[strong_topic]
        self.client.post(
            f"/api/track-d/assessments/{weak.id}/answer",
            headers=self.headers,
            json={"answer": "not the source statement"},
        )
        self.client.post(
            f"/api/track-d/assessments/{strong.id}/answer",
            headers=self.headers,
            json={"answer": strong.correct_answer},
        )

        follow_up = self.client.post(
            "/api/track-d/assessments/adaptive", headers=self.headers, json={}
        )
        self.assertEqual(follow_up.status_code, 200, follow_up.text)
        self.assertEqual(follow_up.json()["selected_topic"], weak_topic)
        self.assertEqual(follow_up.json()["mastery_score"], 0.0)
        self.assertEqual(follow_up.json()["question"]["topic_tag"], weak_topic)
        self.assertNotEqual(follow_up.json()["selected_topic"], strong_topic)

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
