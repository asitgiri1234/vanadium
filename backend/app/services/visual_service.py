"""Visual understanding service.

When OpenAI is configured (recommended), a single vision-LLM call per video
describes the scene *and* reads on-screen text — far more accurate than OCR on
stylized social video.

OCR (Tesseract) is optional fallback only when ENABLE_OCR=true and no API key.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Platform, VisualFrame
from app.utils.llm_utils import content_to_text, parse_json_object
from app.utils.text import clean_text, format_timestamp
from app.utils.ytdlp import base_ytdlp_opts

logger = get_logger(__name__)

# Max frames sent to the vision model (latency/cost control).
_VISION_FRAME_CAP = 3


class VisualService:
    def extract(self, url: str, platform: Platform) -> tuple[list[VisualFrame], str, str]:
        """Return (ocr frames, scene summary, on-screen text from vision)."""
        if not settings.enable_visual:
            return [], "", ""

        work_dir = tempfile.mkdtemp(prefix="vanadium_vis_")
        try:
            video_path = self._download_video(url, work_dir)
            if not video_path:
                return [], "", ""

            frame_paths = self._extract_frames(video_path, work_dir)
            if not frame_paths:
                return [], "", ""

            image_paths = [p for _, p in frame_paths]

            if settings.llm_configured:
                summary, on_screen = self._vision_analyze(image_paths)
                return [], summary, on_screen

            # Offline / no-key fallback: optional OCR only.
            if settings.enable_ocr:
                self._configure_tesseract()
                frames = self._ocr_frames(frame_paths)
                return frames, "", ""

            return [], "", ""
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.warning("Visual extraction failed for %s: %s", url, exc)
            return [], "", ""
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
        opts = base_ytdlp_opts(
            outtmpl=out_tmpl,
            format=(
                f"best[height<={h}][ext=mp4]/best[height<={h}]/"
                "best[ext=mp4]/best"
            ),
        )
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        return path if os.path.exists(path) else None

    def _extract_frames(
        self, video_path: str, work_dir: str
    ) -> list[tuple[float, str]]:
        """Sample frames spread across the video."""
        duration = self._probe_duration(video_path)
        max_frames = max(1, settings.visual_max_frames)
        interval = max(1.5, duration / max_frames) if duration else 2.0

        frames_dir = os.path.join(work_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        out_pattern = os.path.join(frames_dir, "frame_%03d.jpg")

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video_path,
            "-vf", f"fps=1/{interval:.4f}",
            "-frames:v", str(max_frames),
            "-q:v", "4",
            out_pattern,
        ]
        subprocess.run(cmd, check=True, timeout=90)

        results: list[tuple[float, str]] = []
        for i in range(1, max_frames + 1):
            path = os.path.join(frames_dir, f"frame_{i:03d}.jpg")
            if not os.path.exists(path):
                break
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
        from PIL import Image, ImageOps

        frames: list[VisualFrame] = []
        last_text = ""
        for start, path in frame_paths:
            try:
                img = Image.open(path).convert("L")
                w, h = img.size
                if max(w, h) < 1400:
                    img = img.resize((w * 2, h * 2))
                img = ImageOps.autocontrast(img)
                raw = pytesseract.image_to_string(img, config="--psm 6")
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR failed on a frame: %s", exc)
                continue
            text = clean_text(raw)
            if len(text) < 8 or text == last_text:
                continue
            last_text = text
            frames.append(
                VisualFrame(start=start, timestamp=format_timestamp(start), ocr_text=text)
            )
        logger.info("OCR produced %d text frames", len(frames))
        return frames

    def _vision_analyze(self, frame_paths: list[str]) -> tuple[str, str]:
        """One vision call: scene description + on-screen text."""
        if not frame_paths:
            return "", ""
        try:
            from langchain_core.messages import HumanMessage

            from app.services.llm_service import get_vision_llm

            sample = frame_paths[:_VISION_FRAME_CAP]
            content: list[dict] = [
                {
                    "type": "text",
                    "text": (
                        "These are sampled frames from a short social media video. "
                        "Respond with JSON only (no markdown):\n"
                        '{"description": "2-3 sentences: setting, people, actions, mood", '
                        '"on_screen_text": "all visible text overlays/captions verbatim, '
                        'joined with | if multiple, or empty string if none"}'
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

            llm = get_vision_llm(temperature=0.2).bind(
                response_format={"type": "json_object"}
            )
            resp = llm.invoke([HumanMessage(content=content)])
            return self._parse_vision_json(getattr(resp, "content", None))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Vision analysis failed: %s", exc)
            return "", ""

    @staticmethod
    def _parse_vision_json(raw: Any) -> tuple[str, str]:
        try:
            data = parse_json_object(raw)
            return (
                clean_text(str(data.get("description", ""))),
                clean_text(str(data.get("on_screen_text", ""))),
            )
        except ValueError:
            text = content_to_text(raw)
            return clean_text(text[:800]), ""


visual_service = VisualService()
