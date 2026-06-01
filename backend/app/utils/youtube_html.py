"""Parse duration and engagement metrics embedded in YouTube watch-page HTML."""

from __future__ import annotations

import re

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

_WATCH_UA = (
    "Mozilla/5.0 (Linux; Android 10; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

_VIEW_RE = re.compile(r'"viewCount"\s*:\s*"(\d+)"')
_DURATION_RE = re.compile(r'"lengthSeconds"\s*:\s*"(\d+)"')
_LIKE_RE = re.compile(r'"likeCount"\s*:\s*"(\d+)"')
_COMMENT_RE = re.compile(r'"commentCount"\s*:\s*"(\d+)"')


def _first_int(pattern: re.Pattern[str], html: str) -> int | None:
    match = pattern.search(html)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def fetch_youtube_html_metrics(url: str) -> RawMetadata | None:
    """Extract metrics from watch-page HTML when innertube JSON parsing fails."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    for watch_url in (
        f"https://m.youtube.com/watch?v={video_id}",
        f"https://www.youtube.com/watch?v={video_id}",
    ):
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                resp = client.get(
                    watch_url,
                    headers={
                        "User-Agent": _WATCH_UA,
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    cookies={"CONSENT": "YES+cb.20210328-17-p0.en+FX+667"},
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube HTML metrics fetch failed for %s: %s", watch_url, exc)
            continue

        views = _first_int(_VIEW_RE, html)
        duration = _first_int(_DURATION_RE, html)
        likes = _first_int(_LIKE_RE, html)
        comments = _first_int(_COMMENT_RE, html)

        if not views and not duration:
            continue

        logger.info(
            "YouTube HTML metrics for %s: views=%s duration=%s comments=%s",
            video_id,
            views,
            duration,
            comments,
        )
        return RawMetadata(
            platform=Platform.youtube,
            views=views or 0,
            likes=likes,
            comments=comments,
            duration_seconds=duration or 0,
        )

    return None
