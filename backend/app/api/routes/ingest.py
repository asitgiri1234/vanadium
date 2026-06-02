"""Ingestion + analysis retrieval endpoints."""

from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    AnalysisProgress,
    AnalysisSnapshot,
    ComparisonInsights,
    IngestRequest,
    Platform,
    TranscriptLine,
    TranscriptResponse,
    VideoMetadata,
    VideoTranscript,
    VideoVisual,
    VisualResponse,
)
from app.services.ingestion_service import UnsupportedURLError, ingestion_service
from app.store.analysis_store import analysis_store
from app.utils.text import format_timestamp

logger = get_logger(__name__)
router = APIRouter(tags=["ingest"])
_ingest_threads: dict[str, threading.Thread] = {}


def _placeholder_video(slot: str, url: str) -> VideoMetadata:
    platform = Platform.youtube if "youtu" in url.lower() else (
        Platform.instagram if "instagram" in url.lower() else Platform.unknown
    )
    return VideoMetadata(
        video_id=slot,  # type: ignore[arg-type]
        platform=platform,
        url=url,
    )


def _start_ingest_background(payload: IngestRequest, analysis_id: str) -> None:
    def progress(stage: str, patch: dict) -> None:
        analysis_store.update_progress(analysis_id, stage=stage, **patch)

    def run() -> None:
        try:
            ingestion_service.ingest(
                payload.video_a_url,
                payload.video_b_url,
                analysis_id=analysis_id,
                progress_cb=progress,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Background ingest failed for %s", analysis_id)
            analysis_store.update_progress(
                analysis_id,
                status="error",
                stage="error",
                stage_message="Analysis failed",
                error=str(exc)[:300],
            )

    thread = threading.Thread(target=run, daemon=True)
    _ingest_threads[analysis_id] = thread
    thread.start()


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


@router.post("/ingest/start", response_model=AnalysisProgress)
async def ingest_start(payload: IngestRequest) -> AnalysisProgress:
    analysis_id = uuid.uuid4().hex[:10]
    snapshot = AnalysisSnapshot(
        analysis_id=analysis_id,
        videos={
            "A": _placeholder_video("A", payload.video_a_url),
            "B": _placeholder_video("B", payload.video_b_url),
        },
        comparison=ComparisonInsights(ai_pending=True),
    )
    analysis_store.save(snapshot)
    progress = AnalysisProgress(
        analysis_id=analysis_id,
        status="running",
        stage="metadata",
        stage_message="Fetching Metadata...",
    )
    analysis_store.set_progress(progress)
    _start_ingest_background(payload, analysis_id)
    return progress


@router.get("/analysis/{analysis_id}", response_model=AnalysisSnapshot)
async def get_analysis(analysis_id: str) -> AnalysisSnapshot:
    snapshot = analysis_store.get(analysis_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return snapshot


@router.get("/analysis/{analysis_id}/progress", response_model=AnalysisProgress)
async def get_analysis_progress(analysis_id: str) -> AnalysisProgress:
    progress = analysis_store.get_progress(analysis_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return progress


@router.get("/analysis/{analysis_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(analysis_id: str) -> TranscriptResponse:
    snapshot = analysis_store.get(analysis_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stored = analysis_store.get_transcripts(analysis_id) or {}
    transcripts: dict[str, VideoTranscript] = {}
    for slot in ("A", "B"):
        segments = stored.get(slot, [])  # type: ignore[arg-type]
        lines = [
            TranscriptLine(
                start=seg.start,
                timestamp=format_timestamp(seg.start),
                text=seg.text,
            )
            for seg in segments
        ]
        transcripts[slot] = VideoTranscript(
            video_id=slot,  # type: ignore[arg-type]
            platform=snapshot.videos[slot].platform,  # type: ignore[index]
            available=bool(lines),
            segments=lines,
        )
    return TranscriptResponse(
        analysis_id=analysis_id,
        whisper_enabled=settings.enable_whisper,
        transcripts=transcripts,  # type: ignore[arg-type]
    )


@router.get("/analysis/{analysis_id}/visual", response_model=VisualResponse)
async def get_visual(analysis_id: str) -> VisualResponse:
    snapshot = analysis_store.get(analysis_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stored = analysis_store.get_visuals(analysis_id) or {}
    visuals: dict[str, VideoVisual] = {}
    for slot in ("A", "B"):
        visuals[slot] = stored.get(slot) or VideoVisual(  # type: ignore[arg-type]
            video_id=slot,  # type: ignore[arg-type]
            platform=snapshot.videos[slot].platform,  # type: ignore[index]
            available=False,
        )
    return VisualResponse(
        analysis_id=analysis_id,
        enabled=settings.enable_visual,
        vision_enabled=settings.enable_visual and settings.llm_configured,
        visuals=visuals,  # type: ignore[arg-type]
    )
