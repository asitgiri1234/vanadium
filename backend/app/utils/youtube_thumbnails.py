"""YouTube thumbnail frames for cloud visual analysis (no yt-dlp)."""

from __future__ import annotations

import os

import httpx

from app.core.logging import get_logger
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

_THUMB_VARIANTS = (
    "maxresdefault",
    "sddefault",
    "hqdefault",
    "mqdefault",
    "default",
)


def download_youtube_frames(video_id: str, work_dir: str, max_frames: int = 4) -> list[str]:
    """Download up to ``max_frames`` public YouTube thumbnails to ``work_dir``."""
    saved: list[str] = []
    for variant in _THUMB_VARIANTS:
        if len(saved) >= max_frames:
            break
        url = f"https://i.ytimg.com/vi/{video_id}/{variant}.jpg"
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Vanadium/1.0"})
                if resp.status_code != 200 or len(resp.content) < 1000:
                    continue
                path = os.path.join(work_dir, f"yt_frame_{len(saved):02d}.jpg")
                with open(path, "wb") as fh:
                    fh.write(resp.content)
                saved.append(path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("YouTube frame download failed for %s: %s", url, exc)
            continue

    if saved:
        logger.info("YouTube thumbnail frames: %d for %s", len(saved), video_id)
    return saved


def download_youtube_frames_for_url(url: str, work_dir: str, max_frames: int = 4) -> list[str]:
    video_id = extract_youtube_id(url)
    if not video_id:
        return []
    return download_youtube_frames(video_id, work_dir, max_frames=max_frames)
