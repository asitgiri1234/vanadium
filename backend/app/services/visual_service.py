"""Visual understanding service.

For videos where the audio carries little/no information (music-only reels,
text-overlay videos), this extracts meaning from the *frames*:

- **OCR** (Tesseract, local/free): reads on-screen text overlays per frame.
- **Vision summary** (GPT-4o-mini, optional): one holistic scene description
  per video — only when an OpenAI key is configured.

Pipeline: download a low-res copy → sample frames with ffmpeg → OCR each frame
(+ optional vision call). Everything degrades gracefully if a step is missing.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Platform, VisualFrame
from app.utils.text import clean_text, format_timestamp
from app.utils.ytdlp import apply_cookie_options

logger = get_logger(__name__)


class VisualService:
    def extract(self, url: str, platform: Platform) -> tuple[list[VisualFrame], str]:
        """Return (per-frame OCR frames, holistic vision summary)."""
        if not settings.enable_visual:
            return [], ""

        self._configure_tesseract()
        work_dir = tempfile.mkdtemp(prefix="vanadium_vis_")
        try:
            video_path = self._download_video(url, work_dir)
            if not video_path:
                return [], ""

            frame_paths = self._extract_frames(video_path, work_dir)
            if not frame_paths:
                return [], ""

            frames = self._ocr_frames(frame_paths)
            summary = self._vision_summary([p for _, p in frame_paths])
            return frames, summary
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.warning("Visual extraction failed for %s: %s", url, exc)
            return [], ""
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # ----------------------------------------------------------------- #
    @staticmethod
    def _configure_tesseract() -> None:
        if settings.tesseract_cmd:
            import pytesseract

            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    def _download_video(self, url: str, work_dir: str) -> str | None:
        from yt_dlp import YoutubeDL

        h = settings.visual_max_height
        out_tmpl = os.path.join(work_dir, "video.%(ext)s")
        opts = apply_cookie_options(
            {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "outtmpl": out_tmpl,
                "format": (
                    f"best[height<={h}][ext=mp4]/best[height<={h}]/"
                    "best[ext=mp4]/best"
                ),
            }
        )
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        return path if os.path.exists(path) else None

    def _extract_frames(
        self, video_path: str, work_dir: str
    ) -> list[tuple[float, str]]:
        """Sample up to ``visual_max_frames`` frames spread across the video."""
        duration = self._probe_duration(video_path)
        max_frames = max(1, settings.visual_max_frames)
        interval = max(1.0, duration / max_frames) if duration else 2.0

        frames_dir = os.path.join(work_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        out_pattern = os.path.join(frames_dir, "frame_%03d.jpg")

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video_path,
            "-vf", f"fps=1/{interval:.4f}",
            "-frames:v", str(max_frames),
            "-q:v", "3",
            out_pattern,
        ]
        subprocess.run(cmd, check=True, timeout=120)

        results: list[tuple[float, str]] = []
        for i in range(1, max_frames + 1):
            path = os.path.join(frames_dir, f"frame_{i:03d}.jpg")
            if not os.path.exists(path):
                break
            # Approximate timestamp of this sampled frame.
            results.append(((i - 1) * interval, path))
        return results

    @staticmethod
    def _probe_duration(video_path: str) -> float:
        try:
            out = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", video_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            return float(out.stdout.strip())
        except Exception:  # noqa: BLE001
            return 0.0

    def _ocr_frames(self, frame_paths: list[tuple[float, str]]) -> list[VisualFrame]:
        import pytesseract
        from PIL import Image

        frames: list[VisualFrame] = []
        last_text = ""
        for start, path in frame_paths:
            try:
                img = self._preprocess(Image.open(path))
                # psm 11 = "sparse text": find scattered text overlays anywhere.
                data = pytesseract.image_to_data(
                    img, config="--psm 11", output_type=pytesseract.Output.DICT
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR failed on a frame: %s", exc)
                continue
            text = self._words_from_data(data)
            # Skip empty/noise and consecutive duplicate overlays.
            if not text or text == last_text:
                continue
            last_text = text
            frames.append(
                VisualFrame(start=start, timestamp=format_timestamp(start), ocr_text=text)
            )
        logger.info("OCR produced %d text frames", len(frames))
        return frames

    # Floor confidence: drops the most obvious garbage without nuking stylized
    # (low-confidence) headline text, which we instead clean linguistically.
    _MIN_CONF = 30

    def _words_from_data(self, data: dict) -> str:
        """Keep word-like tokens (real letters + a vowel) from image_to_data."""
        words: list[str] = []
        for txt, conf in zip(data.get("text", []), data.get("conf", [])):
            try:
                c = float(conf)
            except (TypeError, ValueError):
                c = -1.0
            token = txt.strip()
            if c < self._MIN_CONF or not self._word_like(token):
                continue
            words.append(token)
        return clean_text(" ".join(words))

    @staticmethod
    def _word_like(token: str) -> bool:
        """A real-ish word: 3+ chars, has a vowel, and is mostly letters."""
        if len(token) < 3:
            return False
        lowered = token.lower()
        if not any(v in lowered for v in "aeiou"):
            return False
        alpha = sum(ch.isalpha() for ch in token)
        return alpha >= 3 and alpha / len(token) >= 0.6

    @staticmethod
    def _preprocess(img):
        """Boost OCR accuracy: grayscale, upscale small text, raise contrast."""
        from PIL import ImageOps

        img = img.convert("L")
        w, h = img.size
        # Upscale so small overlay text is large enough for Tesseract.
        scale = 2 if max(w, h) < 1400 else 1
        if scale > 1:
            img = img.resize((w * scale, h * scale))
        return ImageOps.autocontrast(img)

    # ----------------------------------------------------------------- #
    # Optional vision-LLM scene summary (one call per video).
    # ----------------------------------------------------------------- #
    def _vision_summary(self, frame_paths: list[str]) -> str:
        if not settings.openai_configured or not frame_paths:
            return ""
        try:
            from langchain_core.messages import HumanMessage
            from langchain_openai import ChatOpenAI

            # Cap the number of images sent to control cost/latency.
            sample = frame_paths[:5]
            content: list[dict] = [
                {
                    "type": "text",
                    "text": (
                        "These are sampled frames from a short social video. "
                        "In 2-3 sentences, describe what is shown: the setting, "
                        "people, actions, mood, and any notable visuals. Do not "
                        "transcribe on-screen text verbatim."
                    ),
                }
            ]
            for path in sample:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                )

            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                temperature=0.3,
            )
            resp = llm.invoke([HumanMessage(content=content)])
            return clean_text(getattr(resp, "content", "") or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vision summary failed: %s", exc)
            return ""


visual_service = VisualService()
