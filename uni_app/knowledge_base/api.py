"""Authenticated HTTP routes for Track D ingestion, retrieval and tutoring."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Callable, Optional

import httpx
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse

from uni_app import ai_provider, youtube_utils

from .ingestion import (
    MAX_SOURCE_BYTES,
    DuplicateSourceError,
    InvalidSourceError,
    KnowledgeBaseIngestor,
    SourceIngestionError,
)
from .assessment import AssessmentService, citation_payload, question_payload
from .retrieval import SourceRetriever
from .tutoring import GroundedTutor, TutorResponseError
from .visual_analysis import LocalOCRAnalyzer


logger = logging.getLogger(__name__)
AuthResolver = Callable[[str], int]


def _database_engine(database_url: Optional[str] = None) -> Engine:
    raw = (database_url or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is required for the Track D knowledge base")
    url = make_url(raw)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Track D knowledge retrieval requires PostgreSQL")
    return create_engine(url, pool_pre_ping=True)


def _token(request: Request) -> str:
    direct = (request.headers.get("X-Auth-Token") or "").strip()
    if direct:
        return direct
    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _safe_json(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    return value


class KnowledgeBaseAPI:
    def __init__(
        self,
        *,
        engine: Engine,
        auth_resolver: AuthResolver,
        provider_config: ai_provider.ProviderConfig = ai_provider.CONFIG,
        completion=ai_provider.complete,
        transcript_fetcher=youtube_utils.fetch_transcript_segments,
        visual_analyzer=None,
    ):
        self.engine = engine
        self.auth_resolver = auth_resolver
        self.transcript_fetcher = transcript_fetcher
        self.ingestor = KnowledgeBaseIngestor(
            engine,
            visual_analyzer=visual_analyzer or LocalOCRAnalyzer(),
        )
        self.retriever = SourceRetriever(engine)
        self.assessments = AssessmentService(engine)
        self.tutor = GroundedTutor(
            self.retriever,
            config=provider_config,
            completion=completion,
        )

    def owner(self, request: Request) -> Optional[int]:
        token = _token(request)
        if not token:
            return None
        try:
            owner_id = int(self.auth_resolver(token))
        except Exception:
            logger.warning("Track D authentication failed reason=resolver_error")
            return None
        return owner_id if owner_id > 0 else None

    @staticmethod
    def unauthorized() -> JSONResponse:
        return JSONResponse({"error": "Authentication required."}, status_code=401)

    async def _upload(self, request: Request, source_type: str) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_SOURCE_BYTES + 1_000_000:
                    return JSONResponse({"error": "File exceeds the 25 MB limit."}, status_code=413)
            except ValueError:
                return JSONResponse({"error": "Invalid request size."}, status_code=400)
        try:
            form = await request.form(max_files=1, max_fields=4, max_part_size=MAX_SOURCE_BYTES + 1)
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                return JSONResponse({"error": "A source file is required."}, status_code=400)
            data = await upload.read(MAX_SOURCE_BYTES + 1)
            await upload.close()
            if len(data) > MAX_SOURCE_BYTES:
                return JSONResponse({"error": "File exceeds the 25 MB limit."}, status_code=413)
            title = str(form.get("title") or "")[:255]
            if source_type == "pdf":
                asset = await asyncio.to_thread(
                    self.ingestor.ingest_pdf,
                    owner_id=owner_id,
                    filename=upload.filename or "",
                    data=data,
                    title=title,
                )
            else:
                asset = await asyncio.to_thread(
                    self.ingestor.ingest_pptx,
                    owner_id=owner_id,
                    filename=upload.filename or "",
                    data=data,
                    title=title,
                )
            return JSONResponse(self._asset_payload(owner_id, asset), status_code=201)
        except DuplicateSourceError:
            return JSONResponse({"error": "This source has already been uploaded."}, status_code=409)
        except InvalidSourceError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        except (SourceIngestionError, ValueError):
            logger.warning("Track D ingestion failed type=%s reason=processing_error", source_type)
            return JSONResponse({"error": "The source could not be processed."}, status_code=422)
        except Exception:
            logger.exception("Track D ingestion failed type=%s reason=backend_error", source_type)
            return JSONResponse({"error": "The source could not be processed."}, status_code=500)

    async def upload_pdf(self, request: Request) -> JSONResponse:
        return await self._upload(request, "pdf")

    async def upload_pptx(self, request: Request) -> JSONResponse:
        return await self._upload(request, "pptx")

    async def submit_youtube(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise InvalidSourceError("JSON object required")
            url = str(data.get("url") or "").strip()
            title = str(data.get("title") or "")[:255]
            asset = await asyncio.to_thread(
                self.ingestor.ingest_youtube,
                owner_id=owner_id,
                original_url=url,
                title=title,
                fetcher=self.transcript_fetcher,
            )
            return JSONResponse(self._asset_payload(owner_id, asset), status_code=201)
        except DuplicateSourceError:
            return JSONResponse({"error": "This source has already been uploaded."}, status_code=409)
        except InvalidSourceError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        except (SourceIngestionError, json.JSONDecodeError):
            logger.warning("Track D ingestion failed type=youtube reason=transcript_unavailable")
            return JSONResponse({"error": "A timestamped transcript is unavailable for this video."}, status_code=422)
        except Exception:
            logger.exception("Track D ingestion failed type=youtube reason=backend_error")
            return JSONResponse({"error": "The source could not be processed."}, status_code=500)

    def _asset_payload(self, owner_id: int, asset) -> dict[str, object]:
        units = self.ingestor.list_units(owner_id=owner_id, asset_id=asset.id)
        visuals = self.ingestor.list_visuals(owner_id=owner_id, asset_id=asset.id)
        return {
            "id": asset.id,
            "title": asset.title,
            "source_type": asset.source_type,
            "original_name": asset.original_name,
            "original_url": asset.original_url,
            "external_id": asset.external_id,
            "extraction_status": asset.extraction_status,
            "source_metadata": _safe_json(asset.source_metadata),
            "unit_count": len(units),
            "visual_count": len(visuals),
            "ocr_complete_count": sum(visual.analysis_status == "complete" for visual in visuals),
            "ocr_unavailable_count": sum(visual.analysis_status == "unavailable" for visual in visuals),
        }

    async def list_sources(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        assets = await asyncio.to_thread(self.ingestor.list_assets, owner_id=owner_id)
        return JSONResponse(
            {"sources": [self._asset_payload(owner_id, asset) for asset in assets]}
        )

    async def source_unit(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        try:
            source_unit_id = int(request.path_params["source_unit_id"])
        except (KeyError, TypeError, ValueError):
            return JSONResponse({"error": "Invalid source unit."}, status_code=400)
        unit = await asyncio.to_thread(
            self.ingestor.get_unit,
            owner_id=owner_id,
            source_unit_id=source_unit_id,
        )
        if unit is None:
            return JSONResponse({"error": "Source unit not found."}, status_code=404)
        return JSONResponse(
            {
                "source_unit_id": unit.id,
                "asset_id": unit.asset_id,
                "source_type": unit.source_type,
                "text": unit.extracted_text,
                "locator": _safe_json(unit.source_locator),
                "extraction_status": unit.extraction_status,
            }
        )

    async def search(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        query = str(request.query_params.get("q") or "")
        try:
            limit = int(request.query_params.get("limit") or 6)
            results = await asyncio.to_thread(
                self.retriever.search,
                owner_id=owner_id,
                query=query,
                limit=limit,
            )
        except (InvalidSourceError, TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return JSONResponse(
            {
                "results": [
                    {
                        "source_unit_id": result.source_unit_id,
                        "asset_id": result.asset_id,
                        "source_type": result.source_type,
                        "source_title": result.asset_title,
                        "excerpt": result.excerpt,
                        "locator": _safe_json(result.source_locator),
                        "rank": result.rank,
                    }
                    for result in results
                ]
            }
        )

    async def tutor_answer(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise InvalidSourceError("JSON object required")
            asset_ids = data.get("asset_ids")
            if asset_ids is not None and not isinstance(asset_ids, list):
                raise InvalidSourceError("asset_ids must be a list")
            response = await asyncio.to_thread(
                self.tutor.answer,
                owner_id=owner_id,
                question=str(data.get("question") or ""),
                asset_ids=asset_ids,
            )
            return JSONResponse(
                {
                    "answer": response.answer,
                    "supported": response.supported,
                    "citations": [
                        {
                            "source_unit_id": citation.source_unit_id,
                            "asset_id": citation.asset_id,
                            "source_type": citation.source_type,
                            "source_title": citation.source_title,
                            "label": citation.label,
                            "link": citation.link,
                            "excerpt": citation.excerpt,
                            "locator": _safe_json(citation.locator),
                        }
                        for citation in response.citations
                    ],
                    "retrieved_unit_ids": list(response.retrieved_unit_ids),
                }
            )
        except InvalidSourceError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        except TutorResponseError:
            logger.warning("Track D tutor rejected provider output reason=citation_validation")
            return JSONResponse({"error": "The grounded answer could not be verified."}, status_code=503)
        except (httpx.HTTPError, RuntimeError) as exc:
            failure = ai_provider.failure(exc, "track_d_tutor", self.tutor.config, logger)
            return JSONResponse({"error": str(failure), "error_code": failure.code}, status_code=failure.status)
        except Exception:
            logger.exception("Track D tutor failed reason=backend_error")
            return JSONResponse({"error": "The grounded tutor is temporarily unavailable."}, status_code=500)

    async def generate_assessment(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise InvalidSourceError("JSON object required")
            asset_ids = data.get("asset_ids")
            if asset_ids is not None and not isinstance(asset_ids, list):
                raise InvalidSourceError("asset_ids must be a list")
            generated = await asyncio.to_thread(
                self.assessments.generate,
                owner_id=owner_id,
                asset_ids=asset_ids,
                limit=data.get("limit", 9),
                diagnostic=bool(data.get("diagnostic", False)),
            )
            return JSONResponse({
                "questions": [question_payload(item) for item in generated.questions],
                "created_count": generated.created_count,
                "reused_count": generated.reused_count,
            }, status_code=201)
        except (InvalidSourceError, TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        except Exception:
            logger.exception("Track D assessment generation failed")
            return JSONResponse({"error": "The assessment could not be generated."}, status_code=500)

    async def list_assessments(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        try:
            limit = int(request.query_params.get("limit") or 30)
            questions = await asyncio.to_thread(
                self.assessments.list_questions, owner_id=owner_id, limit=limit
            )
            return JSONResponse({"questions": [question_payload(item) for item in questions]})
        except (InvalidSourceError, TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

    async def answer_assessment(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        try:
            data = await request.json()
            result = await asyncio.to_thread(
                self.assessments.answer,
                owner_id=owner_id,
                question_id=int(request.path_params["question_id"]),
                answer=str(data.get("answer") or ""),
            )
            return JSONResponse({
                "question_id": result.question_id,
                "score": result.score,
                "is_correct": result.is_correct,
                "feedback": result.feedback,
                "citation": result.citation,
                "topic_tag": result.topic_tag,
                "mastery_score": result.mastery_score,
                "attempt_count": result.attempt_count,
            })
        except (InvalidSourceError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

    async def mastery(self, request: Request) -> JSONResponse:
        owner_id = self.owner(request)
        if owner_id is None:
            return self.unauthorized()
        rows = await asyncio.to_thread(self.assessments.mastery, owner_id=owner_id)
        return JSONResponse({"mastery": rows})


def register_knowledge_base_routes(
    app,
    *,
    auth_resolver: AuthResolver,
    engine: Optional[Engine] = None,
) -> KnowledgeBaseAPI:
    service = KnowledgeBaseAPI(
        engine=engine or _database_engine(),
        auth_resolver=auth_resolver,
    )
    add_knowledge_base_routes(app, service)
    return service


def add_knowledge_base_routes(app, service: KnowledgeBaseAPI) -> None:
    app.add_route("/api/track-d/sources/pdf", service.upload_pdf, methods=["POST"])
    app.add_route("/api/track-d/sources/pptx", service.upload_pptx, methods=["POST"])
    app.add_route("/api/track-d/sources/youtube", service.submit_youtube, methods=["POST"])
    app.add_route("/api/track-d/sources", service.list_sources, methods=["GET"])
    app.add_route("/api/track-d/source-units/{source_unit_id:int}", service.source_unit, methods=["GET"])
    app.add_route("/api/track-d/search", service.search, methods=["GET"])
    app.add_route("/api/track-d/tutor", service.tutor_answer, methods=["POST"])
    app.add_route("/api/track-d/assessments", service.generate_assessment, methods=["POST"])
    app.add_route("/api/track-d/assessments", service.list_assessments, methods=["GET"])
    app.add_route("/api/track-d/assessments/{question_id:int}/answer", service.answer_assessment, methods=["POST"])
    app.add_route("/api/track-d/mastery", service.mastery, methods=["GET"])
