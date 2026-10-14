"""Owner-scoped PostgreSQL full-text retrieval for source units."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Optional, Sequence

from sqlalchemy import Engine, func, literal_column, select
from sqlalchemy.orm import Session, sessionmaker

from .ingestion import InvalidSourceError, _require_owner
from .models import SourceAsset, SourceUnit


_QUERY_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]{1,63}")
_QUERY_FILLER = {
    "about", "answer", "could", "describe", "does", "explain", "from", "give", "how",
    "material", "materials", "please", "say", "source", "sources", "tell", "textbook",
    "that", "the", "this", "using", "what", "when", "where", "which", "who", "why",
}


@dataclass(frozen=True, slots=True)
class RetrievedSourceUnit:
    source_unit_id: int
    asset_id: int
    source_type: str
    asset_title: str
    original_url: Optional[str]
    excerpt: str
    extracted_text: str
    source_locator: dict[str, Any]
    rank: float


def _websearch_query(value: str) -> str:
    words = [
        word for word in _QUERY_WORD.findall((value or "").strip())[:20]
        if word.lower() not in _QUERY_FILLER
    ]
    if not words:
        raise InvalidSourceError("search query must contain searchable words")
    return " ".join(words)


class SourceRetriever:
    """Search source text with an owner predicate in the database query itself."""

    def __init__(self, engine: Engine):
        self._sessions = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    def search(
        self,
        *,
        owner_id: int,
        query: str,
        limit: int = 6,
        asset_ids: Optional[Sequence[int]] = None,
    ) -> list[RetrievedSourceUnit]:
        owner_id = _require_owner(owner_id)
        search_text = _websearch_query(query)
        limit = max(1, min(int(limit), 10))
        config = literal_column("'english'::regconfig")
        ts_query = func.websearch_to_tsquery(config, search_text)
        vector = func.to_tsvector(config, func.coalesce(SourceUnit.extracted_text, ""))
        rank = func.ts_rank_cd(vector, ts_query).label("rank")
        excerpt = func.ts_headline(
            config,
            SourceUnit.extracted_text,
            ts_query,
            "StartSel=**, StopSel=**, MaxWords=55, MinWords=15, ShortWord=2",
        ).label("excerpt")
        statement = (
            select(
                SourceUnit.id,
                SourceUnit.asset_id,
                SourceUnit.source_type,
                SourceUnit.extracted_text,
                SourceUnit.source_locator,
                SourceAsset.title,
                SourceAsset.original_url,
                rank,
                excerpt,
            )
            .join(
                SourceAsset,
                (SourceAsset.id == SourceUnit.asset_id)
                & (SourceAsset.owner_id == SourceUnit.owner_id),
            )
            .where(
                SourceUnit.owner_id == owner_id,
                SourceAsset.owner_id == owner_id,
                SourceUnit.extraction_status.in_(("complete", "partial")),
                vector.op("@@")(ts_query),
            )
            .order_by(rank.desc(), SourceUnit.id)
            .limit(limit)
        )
        if asset_ids is not None:
            clean_ids = sorted({int(value) for value in asset_ids if int(value) > 0})
            if not clean_ids:
                return []
            statement = statement.where(SourceUnit.asset_id.in_(clean_ids))

        with self._sessions() as session:
            rows = session.execute(statement).all()
        return [
            RetrievedSourceUnit(
                source_unit_id=int(row.id),
                asset_id=int(row.asset_id),
                source_type=str(row.source_type),
                asset_title=str(row.title or "Untitled source"),
                original_url=str(row.original_url) if row.original_url else None,
                excerpt=str(row.excerpt or row.extracted_text or "")[:2_000],
                extracted_text=str(row.extracted_text or "")[:12_000],
                source_locator=dict(row.source_locator or {}),
                rank=float(row.rank or 0.0),
            )
            for row in rows
        ]
