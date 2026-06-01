"""Transcript extraction.

- **YouTube**: ``youtube-transcript-api`` (fast, no download). Supports both the
  legacy (<=0.6) and new (>=1.0) call styles.
- **Instagram Reels**: ``yt-dlp`` downloads audio, then Whisper transcribes it.
  Production uses **Groq Whisper API** (no local PyTorch). Local dev can use
  ``WHISPER_PROVIDER=local`` with ``openai-whisper`` installed.

All failures degrade to an empty transcript so the rest of the pipeline (metadata,
engagement, comparison) still works.
"""

from __future__ import annotations

import os
import tempfile
import threading

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Platform, TranscriptSegment
from app.services.llm_service import GROQ_BASE_URL
from app.utils.url_utils import extract_youtube_id
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)


class TranscriptService:
    def __init__(self) -> None:
        # Cached local Whisper model (WHISPER_PROVIDER=local only).
        self._whisper_model = None
        self._whisper_lock = threading.Lock()

    def fetch(self, url: str, platform: Platform) -> list[TranscriptSegment]:
        try:
            if platform == Platform.youtube:
                return self._youtube(url)
            if platform == Platform.instagram:
                return self._instagram(url)
        except Exception as exc:  # noqa: BLE001 - best-effort extraction
            logger.warning("Transcript extraction failed for %s: %s", url, exc)
        return []

    def resolve_whisper_backend(self) -> str | None:
        """Which IG transcription backend is active: groq, local, or None."""
        if not settings.enable_whisper:
            return None
        provider = settings.whisper_provider.lower().strip()
        if provider == "groq":
            return "groq" if settings.groq_configured else None
        if provider == "local":
            return "local"
        # auto — prefer Groq cloud (works on Render free tier; no PyTorch RAM)
        if settings.groq_configured:
            return "groq"
        return "local"

    # ----------------------------------------------------------------- #
    # YouTube
    # ----------------------------------------------------------------- #
    def _youtube(self, url: str) -> list[TranscriptSegment]:
        video_id = extract_youtube_id(url)
        if not video_id:
            logger.warning("Could not parse YouTube id from %s", url)
            return []

        raw = self._fetch_youtube_raw(video_id)
        if not raw:
            raw = self._fetch_youtube_captions_ytdlp(url)

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

        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id)
            return [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in fetched
            ]
        except (TypeError, AttributeError):
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube transcript API failed for %s: %s", video_id, exc)

        try:
            return YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube transcript API (legacy) failed for %s: %s", video_id, exc)
            return []

    @staticmethod
    def _fetch_youtube_captions_ytdlp(url: str) -> list[dict]:
        """Fallback: pull auto-generated captions via yt-dlp when the transcript API is blocked."""
        from yt_dlp import YoutubeDL

        try:
            opts = base_ytdlp_opts(skip_download=True)
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube caption fallback (yt-dlp) failed for %s: %s", url, exc)
            return []

        info = info or {}
        captions = info.get("automatic_captions") or info.get("subtitles") or {}
        track = None
        for lang in ("en", "en-US", "en-orig", "a.en"):
            if lang in captions:
                track = captions[lang]
                break
        if not track:
            for lang, entries in captions.items():
                if str(lang).startswith("en"):
                    track = entries
                    break
        if not track:
            return []

        sub_url = next((e.get("url") for e in track if e.get("ext") == "vtt"), None)
        if not sub_url and track:
            sub_url = track[0].get("url")
        if not sub_url:
            return []

        try:
            import httpx

            text = httpx.get(sub_url, timeout=30).text
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube caption download failed for %s: %s", url, exc)
            return []

        return TranscriptService._parse_vtt(text)

    @staticmethod
    def _parse_vtt(vtt: str) -> list[dict]:
        """Minimal WebVTT → transcript segments."""
        segments: list[dict] = []
        block: list[str] = []
        start_sec = 0.0

        def ts_to_sec(ts: str) -> float:
            parts = ts.strip().split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s.replace(",", "."))
            if len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s.replace(",", "."))
            return 0.0

        for line in vtt.splitlines():
            if "-->" in line:
                start_sec = ts_to_sec(line.split("-->")[0])
                block = []
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("WEBVTT") or stripped.isdigit():
                continue
            if stripped.startswith("NOTE"):
                block = []
                continue
            block.append(stripped)
            if block:
                segments.append(
                    {
                        "text": " ".join(block),
                        "start": start_sec,
                        "duration": 0.0,
                    }
                )
                block = []

        # Merge duplicate consecutive lines from VTT cue overlap
        merged: list[dict] = []
        for seg in segments:
            if merged and merged[-1]["text"] == seg["text"]:
                continue
            merged.append(seg)
        return merged

    # ----------------------------------------------------------------- #
    # Instagram (yt-dlp audio -> Groq Whisper API or local Whisper)
    # ----------------------------------------------------------------- #
    def _instagram(self, url: str) -> list[TranscriptSegment]:
        backend = self.resolve_whisper_backend()
        if not backend:
            logger.info(
                "IG transcription skipped (ENABLE_WHISPER=false or no provider/key)."
            )
            return []

        audio_path = self._download_audio(url)
        if not audio_path:
            return []
        try:
            if backend == "groq":
                return self._transcribe_groq(audio_path)
            return self._transcribe_whisper_local(audio_path)
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
        opts = base_ytdlp_opts(
            format="bestaudio/best",
            outtmpl=out_tmpl,
        )
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        return path if os.path.exists(path) else None

    def _transcribe_groq(self, audio_path: str) -> list[TranscriptSegment]:
        """Groq-hosted Whisper — no local PyTorch; works on low-RAM hosts."""
        from openai import OpenAI

        client = OpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL)
        with open(audio_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=settings.groq_whisper_model,
                file=audio_file,
                response_format="verbose_json",
                temperature=0.0,
            )

        segments: list[TranscriptSegment] = []
        raw_segments = getattr(result, "segments", None) or []
        for seg in raw_segments:
            if isinstance(seg, dict):
                text = (seg.get("text") or "").strip()
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", start))
            else:
                text = (getattr(seg, "text", "") or "").strip()
                start = float(getattr(seg, "start", 0.0))
                end = float(getattr(seg, "end", start))
            if not text:
                continue
            segments.append(
                TranscriptSegment(text=text, start=start, duration=max(0.0, end - start))
            )

        if not segments and getattr(result, "text", None):
            segments.append(
                TranscriptSegment(
                    text=str(result.text).strip(),
                    start=0.0,
                    duration=0.0,
                )
            )

        logger.info(
            "Groq Whisper transcript (%s): %d segments",
            settings.groq_whisper_model,
            len(segments),
        )
        return segments

    def _load_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model
        with self._whisper_lock:
            if self._whisper_model is None:
                import whisper  # type: ignore

                logger.info("Loading local Whisper model '%s'…", settings.whisper_model)
                self._whisper_model = whisper.load_model(settings.whisper_model)
        return self._whisper_model

    def _transcribe_whisper_local(self, audio_path: str) -> list[TranscriptSegment]:
        model = self._load_whisper_model()
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
        logger.info("Local Whisper transcript: %d segments", len(segments))
        return segments


transcript_service = TranscriptService()
