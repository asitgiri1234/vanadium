"""Transcript extraction.

- **YouTube**: ``youtube-transcript-api`` (fast, no download). Supports both the
  legacy (<=0.6) and new (>=1.0) call styles.
- **Instagram Reels**: ``yt-dlp`` downloads the audio, then Whisper transcribes
  it. This is heavy and gated behind ``ENABLE_WHISPER`` / availability.

All failures degrade to an empty transcript so the rest of the pipeline (metadata,
engagement, comparison) still works.
"""

from __future__ import annotations

import os
import tempfile

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Platform, TranscriptSegment
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)


class TranscriptService:
    def fetch(self, url: str, platform: Platform) -> list[TranscriptSegment]:
        try:
            if platform == Platform.youtube:
                return self._youtube(url)
            if platform == Platform.instagram:
                return self._instagram(url)
        except Exception as exc:  # noqa: BLE001 - best-effort extraction
            logger.warning("Transcript extraction failed for %s: %s", url, exc)
        return []

    # ----------------------------------------------------------------- #
    # YouTube
    # ----------------------------------------------------------------- #
    def _youtube(self, url: str) -> list[TranscriptSegment]:
        video_id = extract_youtube_id(url)
        if not video_id:
            logger.warning("Could not parse YouTube id from %s", url)
            return []

        raw = self._fetch_youtube_raw(video_id)
        segments: list[TranscriptSegment] = []
        for item in raw:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    text=text,
                    start=float(item.get("start", 0.0) or 0.0),
                    duration=float(item.get("duration", 0.0) or 0.0),
                )
            )
        logger.info("YouTube transcript: %d segments for %s", len(segments), video_id)
        return segments

    @staticmethod
    def _fetch_youtube_raw(video_id: str) -> list[dict]:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

        # New API (>=1.0): instance .fetch() returning objects.
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id)
            return [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in fetched
            ]
        except (TypeError, AttributeError):
            pass

        # Legacy API (<=0.6): classmethod returning list[dict].
        return YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]

    # ----------------------------------------------------------------- #
    # Instagram (yt-dlp audio -> Whisper)
    # ----------------------------------------------------------------- #
    def _instagram(self, url: str) -> list[TranscriptSegment]:
        if not settings.enable_whisper:
            logger.info(
                "Whisper disabled (ENABLE_WHISPER=false); skipping IG transcription."
            )
            return []

        audio_path = self._download_audio(url)
        if not audio_path:
            return []
        try:
            return self._transcribe_whisper(audio_path)
        finally:
            try:
                os.remove(audio_path)
            except OSError:
                pass

    @staticmethod
    def _download_audio(url: str) -> str | None:
        from yt_dlp import YoutubeDL

        tmp_dir = tempfile.mkdtemp(prefix="vanadium_")
        out_tmpl = os.path.join(tmp_dir, "audio.%(ext)s")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": out_tmpl,
            "noplaylist": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        return path if os.path.exists(path) else None

    def _transcribe_whisper(self, audio_path: str) -> list[TranscriptSegment]:
        import whisper  # type: ignore

        model = whisper.load_model(settings.whisper_model)
        result = model.transcribe(audio_path)
        segments: list[TranscriptSegment] = []
        for seg in result.get("segments", []):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start))
            segments.append(
                TranscriptSegment(text=text, start=start, duration=max(0.0, end - start))
            )
        logger.info("Whisper transcript: %d segments", len(segments))
        return segments


transcript_service = TranscriptService()
