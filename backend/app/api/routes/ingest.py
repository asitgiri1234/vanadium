"""Ingestion + analysis retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.core.logging import get_logger
from app.models.schemas import AnalysisSnapshot, IngestRequest
from app.services.ingestion_service import UnsupportedURLError, ingestion_service
from app.store.analysis_store import analysis_store

logger = get_logger(__name__)
router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=AnalysisSnapshot)
async def ingest(payload: IngestRequest) -> AnalysisSnapshot:
    try:
        # Ingestion is blocking (network + CPU), so run it off the event loop.
        return await run_in_threadpool(
            ingestion_service.ingest, payload.video_a_url, payload.video_b_url
        )
    except UnsupportedURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc


@router.get("/analysis/{analysis_id}", response_model=AnalysisSnapshot)
async def get_analysis(analysis_id: str) -> AnalysisSnapshot:
    snapshot = analysis_store.get(analysis_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return snapshot
