"""Ingestion orchestration.

Coordinates the full pipeline for both videos:

    metadata → transcript → engagement → chunk → embed → index → compare

Videos A and B are processed in parallel. The LLM strategist comparison runs
in a background thread so the API returns quickly with rule-based insights;
the AI summary fills in within a few seconds via polling.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.core.config import settings
from app.core.logging import get_logger
from app.core.warmup import warmup_heavy_dependencies
from app.models.schemas import (
    AnalysisSnapshot,
    Platform,
    TranscriptSegment,
    VideoMetadata,
    VideoSlot,
    VideoVisual,
)
from app.services.chunking_service import chunking_service
from app.services.comparison_service import comparison_service, compute_engagement_rate
from app.services.embedding_service import embedding_service
from app.services.metadata_service import metadata_service
from app.services.transcript_service import transcript_service
from app.services.visual_service import visual_service
from app.store.analysis_store import analysis_store
from app.utils.url_utils import detect_platform, is_supported
from app.vectorstore.chroma_store import chroma_store

logger = get_logger(__name__)


class UnsupportedURLError(ValueError):
    pass


class IngestionService:
    def ingest(
        self,
        video_a_url: str,
        video_b_url: str,
        *,
        analysis_id: str | None = None,
        progress_cb: Callable[[str, dict], None] | None = None,
    ) -> AnalysisSnapshot:
        for url in (video_a_url, video_b_url):
            if not is_supported(url):
                raise UnsupportedURLError(
                    f"Unsupported or unrecognised URL: {url!r}. "
                    "Only YouTube and Instagram Reels are supported."
                )

        analysis_id = analysis_id or uuid.uuid4().hex[:10]
        logger.info("Starting ingest %s", analysis_id)
        t_total = time.perf_counter()
        self._progress(progress_cb, "queued", {"stage_message": "Queued"})

        warmup_heavy_dependencies()
        self._progress(progress_cb, "metadata", {"stage_message": "Fetching metadata..."})

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(self._process_video, analysis_id, "A", video_a_url)
            fut_b = pool.submit(self._process_video, analysis_id, "B", video_b_url)
            meta_a, segs_a, vis_a = fut_a.result()
            meta_b, segs_b, vis_b = fut_b.result()
        self._progress(progress_cb, "metadata", {"metadata_complete": True, "stage_message": "Metadata complete"})
        self._progress(progress_cb, "transcript", {"transcript_complete": True, "stage_message": "Transcript complete"})
        self._progress(progress_cb, "embeddings", {"embeddings_complete": True, "stage_message": "Embeddings complete"})

        videos: dict[VideoSlot, VideoMetadata] = {"A": meta_a, "B": meta_b}
        self._store_metadata(analysis_id, videos)
        analysis_store.save_transcripts(analysis_id, {"A": segs_a, "B": segs_b})
        analysis_store.save_visuals(analysis_id, {"A": vis_a, "B": vis_b})

        t_comp = time.perf_counter()
        self._progress(progress_cb, "comparison", {"stage_message": "Building comparison..."})
        comparison = comparison_service.build_insights(
            meta_a, meta_b, segs_a, segs_b, vis_a, vis_b
        )
        logger.info("Comparison: %.2fs", time.perf_counter() - t_comp)
        self._progress(
            progress_cb,
            "comparison",
            {"comparison_complete": True, "stage_message": "Analysis complete"},
        )

        snapshot = AnalysisSnapshot(
            analysis_id=analysis_id,
            videos=videos,
            comparison=comparison,
        )
        analysis_store.save(snapshot)
        logger.info("Ingest %s complete (ai_pending=%s)", analysis_id, comparison.ai_pending)

        if settings.llm_configured:
            self._progress(
                progress_cb,
                "strategist",
                {
                    "stage_message": "Generating strategist summary...",
                    "strategist_complete": False,
                },
            )
            threading.Thread(
                target=self._run_llm_comparison,
                args=(
                    analysis_id,
                    meta_a,
                    meta_b,
                    segs_a,
                    segs_b,
                    vis_a,
                    vis_b,
                    comparison,
                    progress_cb,
                ),
                daemon=True,
            ).start()
        else:
            self._progress(
                progress_cb,
                "done",
                {"status": "done", "stage_message": "Analysis ready", "strategist_complete": True},
            )

        logger.info("Total ingest %s: %.2fs", analysis_id, time.perf_counter() - t_total)

        return snapshot

    def _run_llm_comparison(
        self,
        analysis_id: str,
        meta_a: VideoMetadata,
        meta_b: VideoMetadata,
        segs_a: list[TranscriptSegment],
        segs_b: list[TranscriptSegment],
        vis_a: VideoVisual,
        vis_b: VideoVisual,
        base_comparison,
        progress_cb: Callable[[str, dict], None] | None = None,
    ) -> None:
        try:
            t_llm = time.perf_counter()
            logger.info("Background LLM comparison for %s", analysis_id)
            updated = comparison_service.build_llm_insights(
                meta_a, meta_b, segs_a, segs_b, vis_a, vis_b, base_comparison
            )
            analysis_store.update_comparison(analysis_id, updated)
            logger.info("Strategist Summary: %.2fs", time.perf_counter() - t_llm)
            self._progress(
                progress_cb,
                "done",
                {
                    "status": "done",
                    "stage_message": "Advanced AI Strategist Analysis Ready",
                    "strategist_complete": True,
                },
            )
            logger.info("LLM comparison done for %s", analysis_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Background LLM comparison failed for %s", analysis_id)
            analysis_store.update_comparison(
                analysis_id,
                base_comparison.model_copy(
                    update={"ai_pending": False, "ai_error": str(exc)[:300]}
                ),
            )
            self._progress(
                progress_cb,
                "error",
                {
                    "status": "error",
                    "error": str(exc)[:300],
                    "stage_message": "Strategist summary failed",
                },
            )

    # ----------------------------------------------------------------- #
    def _process_video(
        self, analysis_id: str, slot: VideoSlot, url: str
    ) -> tuple[VideoMetadata, list[TranscriptSegment], VideoVisual]:
        platform = detect_platform(url)

        t_meta = time.perf_counter()
        raw = metadata_service.fetch(url)
        logger.info("Metadata (%s): %.2fs", slot, time.perf_counter() - t_meta)
        ig_media = raw.raw if isinstance(raw.raw, dict) else None
        # Transcript extraction and visual extraction are independent once metadata is loaded.
        # Run them in parallel to cut end-to-end ingest latency.
        with ThreadPoolExecutor(max_workers=2) as pool:
            t_trans = time.perf_counter()
            fut_segments = pool.submit(
                transcript_service.fetch, url, platform, ig_media=ig_media
            )
            t_vis = time.perf_counter()
            fut_visual = pool.submit(
                self._build_visual,
                analysis_id,
                slot,
                url,
                platform,
                fallback_thumbnail=raw.thumbnail,
                ig_media=ig_media,
            )
            segments = fut_segments.result()
            visual = fut_visual.result()
            logger.info("Transcript (%s): %.2fs", slot, time.perf_counter() - t_trans)
            logger.info("Visual (%s): %.2fs", slot, time.perf_counter() - t_vis)

        duration = raw.duration_seconds
        if duration == 0 and segments:
            last = max(segments, key=lambda s: s.start + s.duration)
            duration = int(last.start + last.duration)

        engagement = compute_engagement_rate(raw.likes, raw.comments, raw.views)

        t_chunk = time.perf_counter()
        chunks = chunking_service.chunk(segments, analysis_id, slot, platform)
        logger.info("Chunk generation (%s): %.2fs", slot, time.perf_counter() - t_chunk)
        if chunks:
            t_embed = time.perf_counter()
            embeddings = embedding_service.embed_documents([c.text for c in chunks])
            logger.info("Embeddings (%s): %.2fs", slot, time.perf_counter() - t_embed)
            t_vec = time.perf_counter()
            chroma_store.upsert_chunks(chunks, embeddings)
            logger.info("Vector Store (%s): %.2fs", slot, time.perf_counter() - t_vec)

        metadata = VideoMetadata(
            video_id=slot,
            platform=platform if platform != Platform.unknown else raw.platform,
            url=url,
            title=raw.title,
            creator=raw.creator,
            creator_url=raw.creator_url,
            follower_count=raw.follower_count if raw.follower_count and raw.follower_count > 0 else None,
            thumbnail=raw.thumbnail,
            views=raw.views,
            likes=raw.likes,
            comments=raw.comments,
            duration_seconds=duration,
            upload_date=raw.upload_date,
            hashtags=raw.hashtags,
            engagement_rate=engagement,
            transcript_available=bool(segments),
            chunk_count=len(chunks),
        )
        logger.info(
            "Video %s (%s): %d chunks, engagement %.2f%%",
            slot, platform.value, len(chunks), engagement,
        )
        return metadata, segments, visual

    def _build_visual(
        self,
        analysis_id: str,
        slot: VideoSlot,
        url: str,
        platform: Platform,
        *,
        fallback_thumbnail: str | None = None,
        ig_media: dict | None = None,
    ) -> VideoVisual:
        if not settings.enable_visual:
            return VideoVisual(video_id=slot, platform=platform, available=False)

        frames, summary, on_screen = visual_service.extract(
            url,
            platform,
            fallback_thumbnail=fallback_thumbnail,
            ig_media=ig_media,
        )
        available = bool(frames or summary or on_screen)

        if available:
            parts: list[str] = []
            if summary:
                parts.append(f"Scene description: {summary}")
            if on_screen:
                parts.append(f"On-screen text: {on_screen}")
            ocr_joined = " | ".join(f.ocr_text for f in frames if f.ocr_text)
            if ocr_joined:
                parts.append(f"On-screen text: {ocr_joined}")
            text = "\n".join(parts)
            if text.strip():
                emb = embedding_service.embed_documents([text])[0]
                chroma_store.upsert_visual(analysis_id, slot, platform, text, emb)

        return VideoVisual(
            video_id=slot,
            platform=platform,
            available=available,
            frames=frames,
            visual_summary=summary,
            on_screen_text=on_screen,
        )

    def _store_metadata(
        self, analysis_id: str, videos: dict[VideoSlot, VideoMetadata]
    ) -> None:
        t_embed = time.perf_counter()
        slots = sorted(videos.keys())
        cards = [videos[slot].to_card_text() for slot in slots]
        embeddings = embedding_service.embed_documents(cards)
        logger.info("Embeddings (metadata): %.2fs", time.perf_counter() - t_embed)
        t_vec = time.perf_counter()
        chroma_store.upsert_metadata(analysis_id, videos, embeddings)
        logger.info("Vector Store (metadata): %.2fs", time.perf_counter() - t_vec)

    @staticmethod
    def _progress(
        progress_cb: Callable[[str, dict], None] | None,
        stage: str,
        patch: dict,
    ) -> None:
        if progress_cb is not None:
            progress_cb(stage, patch)


ingestion_service = IngestionService()
