"""Deterministic, cited assessment generation and transparent mastery scoring."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import random
import re
from typing import Any, Optional, Sequence

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from .ingestion import InvalidSourceError, _require_owner
from .models import (
    AssessmentAttempt,
    AssessmentQuestion,
    SourceAsset,
    SourceUnit,
    TopicMastery,
)
from .retrieval import RetrievedSourceUnit
from .tutoring import GroundedCitation, _citation_for


QUESTION_TYPES = ("mcq", "short_answer", "numerical")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_NUMBER = re.compile(r"(?<![\w.])([-+]?\d+(?:\.\d+)?)\s*([A-Za-z%°/²³-]{0,16})")
_STOPWORDS = {
    "about", "after", "also", "because", "been", "before", "being", "between", "could",
    "does", "during", "each", "from", "have", "into", "more", "most", "other", "should",
    "source", "system", "than", "that", "their", "there", "these", "they", "this", "through",
    "using", "what", "when", "where", "which", "while", "with", "would",
}


@dataclass(frozen=True, slots=True)
class AssessmentGeneration:
    questions: tuple[AssessmentQuestion, ...]
    created_count: int
    reused_count: int


@dataclass(frozen=True, slots=True)
class AssessmentResult:
    question_id: int
    score: float
    is_correct: bool
    feedback: str
    citation: dict[str, Any]
    topic_tag: str
    mastery_score: float
    attempt_count: int


def _sentences(text: str) -> list[str]:
    return [
        value.strip()
        for value in _SENTENCE.split((text or "").replace("[Extracted visual text]", ""))
        if 24 <= len(value.strip()) <= 320
    ]


def _keywords(text: str, *, limit: int = 5) -> list[str]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for raw in _WORD.findall(text.lower()):
        word = raw.strip("'-")
        if len(word) < 4 or word in _STOPWORDS:
            continue
        if word not in counts:
            order.append(word)
            counts[word] = 0
        counts[word] += 1
    ranked = sorted(order, key=lambda word: (-counts[word], order.index(word)))
    return ranked[:limit]


def _question_fingerprint(source_unit_id: int, question_type: str, prompt: str, answer: str) -> str:
    return sha256(
        json.dumps(
            [source_unit_id, question_type, prompt, answer],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _citation(unit: SourceUnit, asset: SourceAsset, excerpt: str) -> GroundedCitation:
    return _citation_for(
        RetrievedSourceUnit(
            source_unit_id=unit.id,
            asset_id=asset.id,
            source_type=unit.source_type,
            asset_title=asset.title,
            original_url=asset.original_url,
            excerpt=excerpt[:2_000],
            extracted_text=unit.extracted_text,
            source_locator=dict(unit.source_locator or {}),
            rank=1.0,
        )
    )


def citation_payload(citation: GroundedCitation) -> dict[str, Any]:
    return {
        "source_unit_id": citation.source_unit_id,
        "asset_id": citation.asset_id,
        "source_type": citation.source_type,
        "source_title": citation.source_title,
        "label": citation.label,
        "link": citation.link,
        "excerpt": citation.excerpt,
        "locator": citation.locator,
    }


def question_payload(question: AssessmentQuestion) -> dict[str, Any]:
    return {
        "id": question.id,
        "question_type": question.question_type,
        "prompt": question.prompt,
        "options": list(question.options or []),
        "topic_tag": question.topic_tag,
        "difficulty": question.difficulty,
        "citation": dict(question.citation or {}),
        "diagnostic": bool(question.diagnostic),
    }


class AssessmentService:
    """Build questions from source sentences and update cumulative topic mastery."""

    def __init__(self, engine: Engine):
        self._sessions = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    def _source_rows(
        self,
        session: Session,
        *,
        owner_id: int,
        asset_ids: Optional[Sequence[int]],
    ) -> list[tuple[SourceUnit, SourceAsset]]:
        statement = (
            select(SourceUnit, SourceAsset)
            .join(
                SourceAsset,
                (SourceAsset.id == SourceUnit.asset_id)
                & (SourceAsset.owner_id == SourceUnit.owner_id),
            )
            .where(
                SourceUnit.owner_id == owner_id,
                SourceAsset.owner_id == owner_id,
                SourceUnit.extraction_status.in_(("complete", "partial")),
            )
            .order_by(SourceUnit.asset_id, SourceUnit.unit_index)
        )
        if asset_ids is not None:
            try:
                clean_ids = sorted({int(value) for value in asset_ids if int(value) > 0})
            except (TypeError, ValueError) as exc:
                raise InvalidSourceError("asset_ids must contain positive integers") from exc
            if not clean_ids:
                return []
            statement = statement.where(SourceUnit.asset_id.in_(clean_ids))
        return [(unit, asset) for unit, asset in session.execute(statement).all()]

    def generate(
        self,
        *,
        owner_id: int,
        asset_ids: Optional[Sequence[int]] = None,
        limit: int = 9,
        diagnostic: bool = False,
    ) -> AssessmentGeneration:
        owner_id = _require_owner(owner_id)
        limit = max(1, min(int(limit), 15))
        with self._sessions.begin() as session:
            rows = self._source_rows(session, owner_id=owner_id, asset_ids=asset_ids)
            if not rows:
                raise InvalidSourceError("No processed source material is available for assessment.")
            sentence_pool = [sentence for unit, _asset in rows for sentence in _sentences(unit.extracted_text)]
            candidates: list[dict[str, Any]] = []
            for unit, asset in rows:
                unit_sentences = _sentences(unit.extracted_text)
                if not unit_sentences:
                    continue
                target = unit_sentences[0]
                keywords = _keywords(target)
                topic = (keywords[0] if keywords else asset.title or unit.source_type).lower()[:120]
                citation = citation_payload(_citation(unit, asset, target))

                short_prompt = f"Using the cited source, explain the key statement about {topic}."
                candidates.append(
                    {
                        "unit": unit,
                        "type": "short_answer",
                        "prompt": short_prompt,
                        "options": [],
                        "answer": target,
                        "metadata": {"keywords": keywords, "threshold": 0.6},
                        "topic": topic,
                        "difficulty": "medium",
                        "citation": citation,
                    }
                )

                distractors = [value for value in sentence_pool if value != target]
                unique_distractors = list(dict.fromkeys(distractors))
                if len(unique_distractors) >= 3:
                    options = [target, *unique_distractors[:3]]
                    seed = int(sha256(f"{unit.id}:{target}".encode()).hexdigest()[:12], 16)
                    random.Random(seed).shuffle(options)
                    candidates.append(
                        {
                            "unit": unit,
                            "type": "mcq",
                            "prompt": f"Which statement appears in the cited source about {topic}?",
                            "options": options,
                            "answer": target,
                            "metadata": {},
                            "topic": topic,
                            "difficulty": "easy",
                            "citation": citation,
                        }
                    )

                for sentence in unit_sentences:
                    match = _NUMBER.search(sentence)
                    if not match:
                        continue
                    expected = float(match.group(1))
                    unit_label = match.group(2).strip()
                    prompt = "What numerical value is stated in the cited passage?"
                    if unit_label:
                        prompt += f" Answer using {unit_label}."
                    candidates.append(
                        {
                            "unit": unit,
                            "type": "numerical",
                            "prompt": prompt,
                            "options": [],
                            "answer": str(expected),
                            "metadata": {
                                "expected": expected,
                                "unit": unit_label,
                                "tolerance": max(abs(expected) * 0.01, 0.01),
                            },
                            "topic": topic,
                            "difficulty": "medium",
                            "citation": citation_payload(_citation(unit, asset, sentence)),
                        }
                    )
                    break

            if diagnostic:
                buckets = {
                    question_type: [item for item in candidates if item["type"] == question_type]
                    for question_type in QUESTION_TYPES
                }
                ordered: list[dict[str, Any]] = []
                while any(buckets.values()):
                    for question_type in QUESTION_TYPES:
                        if buckets[question_type]:
                            ordered.append(buckets[question_type].pop(0))
                candidates = ordered
            candidates = candidates[:limit]
            if not candidates:
                raise InvalidSourceError("The sources do not contain enough readable text for assessment.")

            selected: list[AssessmentQuestion] = []
            created = 0
            reused = 0
            for item in candidates:
                fingerprint = _question_fingerprint(
                    item["unit"].id, item["type"], item["prompt"], item["answer"]
                )
                question = session.scalar(
                    select(AssessmentQuestion).where(
                        AssessmentQuestion.owner_id == owner_id,
                        AssessmentQuestion.fingerprint == fingerprint,
                    )
                )
                if question is None:
                    question = AssessmentQuestion(
                        owner_id=owner_id,
                        source_unit_id=item["unit"].id,
                        asset_id=item["unit"].asset_id,
                        question_type=item["type"],
                        prompt=item["prompt"],
                        options=item["options"],
                        correct_answer=item["answer"],
                        answer_metadata=item["metadata"],
                        topic_tag=item["topic"],
                        difficulty=item["difficulty"],
                        citation=item["citation"],
                        fingerprint=fingerprint,
                        diagnostic=diagnostic,
                    )
                    session.add(question)
                    session.flush()
                    created += 1
                else:
                    if diagnostic and not question.diagnostic:
                        question.diagnostic = True
                        session.add(question)
                    reused += 1
                selected.append(question)
            return AssessmentGeneration(tuple(selected), created, reused)

    def list_questions(self, *, owner_id: int, limit: int = 30) -> list[AssessmentQuestion]:
        owner_id = _require_owner(owner_id)
        limit = max(1, min(int(limit), 100))
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(AssessmentQuestion)
                    .where(AssessmentQuestion.owner_id == owner_id)
                    .order_by(AssessmentQuestion.id.desc())
                    .limit(limit)
                )
            )

    def answer(self, *, owner_id: int, question_id: int, answer: str) -> AssessmentResult:
        owner_id = _require_owner(owner_id)
        submitted = (answer or "").strip()
        if not submitted or len(submitted) > 4_000:
            raise InvalidSourceError("An answer between 1 and 4000 characters is required.")
        with self._sessions.begin() as session:
            question = session.scalar(
                select(AssessmentQuestion).where(
                    AssessmentQuestion.id == int(question_id),
                    AssessmentQuestion.owner_id == owner_id,
                )
            )
            if question is None:
                raise InvalidSourceError("Assessment question was not found.")

            if question.question_type == "mcq":
                score = 1.0 if submitted == question.correct_answer else 0.0
            elif question.question_type == "numerical":
                match = _NUMBER.search(submitted)
                expected = float(question.answer_metadata.get("expected", question.correct_answer))
                tolerance = float(question.answer_metadata.get("tolerance", 0.01))
                score = 1.0 if match and math.isclose(float(match.group(1)), expected, abs_tol=tolerance) else 0.0
            else:
                expected_keywords = [str(value).lower() for value in question.answer_metadata.get("keywords", [])]
                submitted_words = set(_keywords(submitted, limit=30))
                score = (
                    sum(keyword in submitted_words for keyword in expected_keywords) / len(expected_keywords)
                    if expected_keywords
                    else 0.0
                )
            score = round(max(0.0, min(float(score), 1.0)), 4)
            threshold = float(question.answer_metadata.get("threshold", 0.8))
            is_correct = score >= threshold
            label = str(question.citation.get("label") or "the cited source")
            if is_correct:
                feedback = f"Correct. Evidence: {label}."
            else:
                feedback = f"Review {label}. Expected source statement: {question.correct_answer}"

            session.add(
                AssessmentAttempt(
                    owner_id=owner_id,
                    question_id=question.id,
                    submitted_answer=submitted,
                    score=score,
                    is_correct=is_correct,
                    feedback=feedback,
                )
            )
            mastery = session.scalar(
                select(TopicMastery)
                .where(
                    TopicMastery.owner_id == owner_id,
                    TopicMastery.topic_tag == question.topic_tag,
                )
                .with_for_update()
            )
            if mastery is None:
                mastery = TopicMastery(
                    owner_id=owner_id,
                    topic_tag=question.topic_tag,
                    mastery_score=0.0,
                    attempt_count=0,
                    correct_count=0,
                )
            previous_total = mastery.mastery_score * mastery.attempt_count
            mastery.attempt_count += 1
            mastery.correct_count += int(is_correct)
            mastery.mastery_score = round(
                (previous_total + score * 100.0) / mastery.attempt_count,
                2,
            )
            session.add(mastery)
            session.flush()
            return AssessmentResult(
                question_id=question.id,
                score=score,
                is_correct=is_correct,
                feedback=feedback,
                citation=dict(question.citation or {}),
                topic_tag=question.topic_tag,
                mastery_score=mastery.mastery_score,
                attempt_count=mastery.attempt_count,
            )

    def mastery(self, *, owner_id: int) -> list[dict[str, Any]]:
        owner_id = _require_owner(owner_id)
        with self._sessions() as session:
            rows = list(
                session.scalars(
                    select(TopicMastery)
                    .where(TopicMastery.owner_id == owner_id)
                    .order_by(TopicMastery.mastery_score, TopicMastery.topic_tag)
                )
            )
        return [
            {
                "topic_tag": row.topic_tag,
                "mastery_score": row.mastery_score,
                "attempt_count": row.attempt_count,
                "correct_count": row.correct_count,
                "weak": row.mastery_score < 70.0,
                "recommendation": (
                    f"Review the cited source material for {row.topic_tag} and retry a question."
                    if row.mastery_score < 70.0
                    else f"Continue with a harder question on {row.topic_tag}."
                ),
            }
            for row in rows
        ]
