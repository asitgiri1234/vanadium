"""YouTube Innertube internal API — reliable metadata on cloud/datacenter IPs.

Uses the public MWEB client (same endpoint the mobile site calls). Does not
require an API key, cookies, or HTML scraping.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.url_utils import extract_youtube_id

logger = get_logger(__name__)

# Public innertube key embedded in YouTube's web/mobile clients.
_INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

_MWEB_CLIENT = {
    "clientName": "MWEB",
    "clientVersion": "2.20240405.01.00",
    "hl": "en",
    "gl": "US",
}

_LIKE_RE = re.compile(r'"likeCount"\s*:\s*"(\d+)"')
_COMMENT_RE = re.compile(r'"commentCount"\s*:\s*"(\d+)"')


def _parse_upload_date(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


def _metric_from_micro_or_json(
    micro: dict[str, Any], html_blob: str, key: str, pattern: re.Pattern[str]
) -> int | None:
    raw = micro.get(key)
    if raw is not None:
        try:
            n = int(raw)
            return n if n >= 0 else None
        except (TypeError, ValueError):
            pass
    match = pattern.search(html_blob)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def fetch_youtube_innertube_metadata(url: str) -> RawMetadata | None:
    """Fetch full YouTube metadata via the innertube player endpoint."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    payload = {
        "context": {"client": _MWEB_CLIENT},
        "videoId": video_id,
    }

    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                f"https://www.youtube.com/youtubei/v1/player?key={_INNERTUBE_API_KEY}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": (
                        "Mozilla/5.0 (Linux; Android 10; Mobile) "
                        "AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("YouTube innertube failed for %s: %s", url, exc)
        return None

    details = data.get("videoDetails") or {}
    title = (details.get("title") or "").strip()
    if not title:
        status = (data.get("playabilityStatus") or {}).get("status")
        logger.warning(
            "YouTube innertube: no title for %s (playability=%s)", video_id, status
        )
        return None

    micro = (data.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    blob = json.dumps(data)

    channel_id = details.get("channelId")
    thumbnails = details.get("thumbnail", {}).get("thumbnails") or []
    thumbnail = thumbnails[-1].get("url") if thumbnails else None
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    views = int(details.get("viewCount") or 0)
    duration = int(details.get("lengthSeconds") or 0)
    likes = _metric_from_micro_or_json(micro, blob, "likeCount", _LIKE_RE)
    comments = _metric_from_micro_or_json(micro, blob, "commentCount", _COMMENT_RE)

    return RawMetadata(
        platform=Platform.youtube,
        title=title,
        creator=(details.get("author") or "Unknown creator").strip(),
        creator_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
        thumbnail=thumbnail,
        views=views,
        likes=likes,
        comments=comments,
        duration_seconds=duration,
        upload_date=_parse_upload_date(micro.get("publishDate") or micro.get("uploadDate")),
        description=(details.get("shortDescription") or "").strip(),
    )
