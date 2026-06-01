"""Transcript extraction.

- **YouTube**: caption APIs (Vercel proxy on cloud) → **Groq Whisper** on audio if empty.
- **Instagram Reels**: download audio → **Groq Whisper** (same GROQ_API_KEY).
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
from app.utils.youtube_captions import fetch_youtube_transcript_raw
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)


class TranscriptService:
    def __init__(self) -> None:
        self._whisper_model = None
        self._whisper_lock = threading.Lock()

    def fetch(self, url: str, platform: Platform) -> list[TranscriptSegment]:
        try:
            if platform == Platform.youtube:
                return self._youtube(url)
            if platform == Platform.instagram:
                return self._instagram(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Transcript extraction failed for %s: %s", url, exc)
        return []

    def resolve_whisper_backend(self) -> str | None:
        if not settings.enable_whisper:
            return None
        provider = settings.whisper_provider.lower().strip()
        if provider == "groq":
            return "groq" if settings.groq_configured else None
        if provider == "local":
            return "local"
        if settings.groq_configured:
            return "groq"
        return "local"

    def _youtube(self, url: str) -> list[TranscriptSegment]:
        video_id = extract_youtube_id(url)
        if not video_id:
            logger.warning("Could not parse YouTube id from %s", url)
            return []

        raw = fetch_youtube_transcript_raw(url)

        if not raw and settings.enable_whisper:
            raw = self._fetch_youtube_whisper(url)

        if not raw and not is_youtube_cloud_host():
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

    def _fetch_youtube_whisper(self, url: str) -> list[dict]:
        """Groq/local Whisper fallback when caption APIs are blocked."""
        backend = self.resolve_whisper_backend()
        if not backend:
            return []

        audio_path = self._download_youtube_audio(url)
        if not audio_path:
            return []

        original = audio_path
        trimmed = self._trim_audio_for_whisper(original)
        path_for_whisper = trimmed or original

        try:
            if backend == "groq":
                segments = self._transcribe_groq(path_for_whisper)
            else:
                segments = self._transcribe_whisper_local(path_for_whisper)
            return [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in segments
            ]
        finally:
            for path in {original, trimmed}:
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    @staticmethod
    def _download_youtube_audio(url: str) -> str | None:
        from yt_dlp import YoutubeDL

        from app.utils.youtube_media import download_youtube_audio

        tmp_dir = tempfile.mkdtemp(prefix="vanadium_yt_")
        out_tmpl = os.path.join(tmp_dir, "audio.%(ext)s")
        try:
            opts = base_ytdlp_opts(
                format="bestaudio/best",
                outtmpl=out_tmpl,
            )
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
            if os.path.exists(path):
                return path
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube audio download (yt-dlp) failed for %s: %s", url, exc)

        direct_path = os.path.join(tmp_dir, "audio.m4a")
        if download_youtube_audio(url, direct_path):
            return direct_path
        return None

    @staticmethod
    def _fetch_youtube_captions_ytdlp(url: str) -> list[dict]:
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

        from app.utils.youtube_captions import _parse_vtt

        return _parse_vtt(text)

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

        original = audio_path
        trimmed = self._trim_audio_for_whisper(original)
        path_for_whisper = trimmed or original

        try:
            if backend == "groq":
                return self._transcribe_groq(path_for_whisper)
            return self._transcribe_whisper_local(path_for_whisper)
        finally:
            for path in {original, trimmed}:
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    @staticmethod
    def _download_audio(url: str) -> str | None:
        from yt_dlp import YoutubeDL

        from app.utils.instagram_media import download_instagram_audio

        tmp_dir = tempfile.mkdtemp(prefix="vanadium_")
        out_tmpl = os.path.join(tmp_dir, "audio.%(ext)s")
        opts = base_ytdlp_opts(format="bestaudio/best", outtmpl=out_tmpl)
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
            if os.path.exists(path):
                return path
        except Exception as exc:  # noqa: BLE001
            logger.warning("IG audio download (yt-dlp) failed for %s: %s", url, exc)

        direct_path = os.path.join(tmp_dir, "audio.m4a")
        if download_instagram_audio(url, direct_path):
            return direct_path
        return None

    @staticmethod
    def _trim_audio_for_whisper(audio_path: str) -> str | None:
        """Trim long audio so Groq Whisper + ingest finish within Render timeouts."""
        max_sec = max(60, settings.whisper_max_audio_seconds)
        out_path = audio_path.rsplit(".", 1)[0] + "_trim.m4a"
        try:
            import subprocess

            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            duration = float(probe.stdout.strip() or 0)
            if duration <= max_sec:
                return None

            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", audio_path,
                    "-t", str(max_sec),
                    "-ac", "1",
                    "-ar", "16000",
                    out_path,
                ],
                check=True,
                timeout=120,
            )
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                logger.info(
                    "Trimmed audio for Whisper: %.0fs → %ds cap",
                    duration,
                    max_sec,
                )
                return out_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("Audio trim for Whisper failed: %s", exc)
        return None

    def _transcribe_groq(self, audio_path: str) -> list[TranscriptSegment]:
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
