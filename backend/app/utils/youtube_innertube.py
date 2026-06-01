"""YouTube Innertube internal API — reliable metadata on cloud/datacenter IPs."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.raw_metadata import RawMetadata
from app.models.schemas import Platform
from app.utils.url_utils import extract_youtube_id
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_proxy import fetch_frontend_proxy

logger = get_logger(__name__)

_INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

_INNERTUBE_ENDPOINTS = (
    "https://youtubei.googleapis.com/youtubei/v1/player",
    "https://www.youtube.com/youtubei/v1/player",
)

# Try multiple clients — MWEB works from most IPs; others as fallback.
_INNERTUBE_CLIENTS: list[dict[str, Any]] = [
    {
        "clientName": "MWEB",
        "clientVersion": "2.20240405.01.00",
        "hl": "en",
        "gl": "US",
    },
    {
        "clientName": "WEB",
        "clientVersion": "2.20240405.00.00",
        "hl": "en",
        "gl": "US",
    },
    {
        "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
        "clientVersion": "2.0",
        "hl": "en",
        "gl": "US",
    },
]

_LIKE_RE = re.compile(r'"likeCount"\s*:\s*"(\d+)"')
_COMMENT_RE = re.compile(r'"commentCount"\s*:\s*"(\d+)"')
_VIEW_RE = re.compile(r'"viewCount"\s*:\s*"(\d+)"')
_DURATION_RE = re.compile(r'"lengthSeconds"\s*:\s*"(\d+)"')

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Origin": "https://www.youtube.com",
    "Referer": "https://www.youtube.com/",
}


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
    micro: dict[str, Any], blob: str, key: str, pattern: re.Pattern[str]
) -> int | None:
    raw = micro.get(key)
    if raw is not None:
        try:
            n = int(raw)
            return n if n >= 0 else None
        except (TypeError, ValueError):
            pass
    match = pattern.search(blob)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _regex_int(pattern: re.Pattern[str], blob: str) -> int | None:
    match = pattern.search(blob)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _parse_innertube_response(data: dict[str, Any], video_id: str) -> RawMetadata | None:
    details = data.get("videoDetails") or {}
    micro = (data.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    blob = json.dumps(data)

    title = (details.get("title") or micro.get("title") or "").strip()
    views = int(details.get("viewCount") or 0) or (_regex_int(_VIEW_RE, blob) or 0)
    duration = int(details.get("lengthSeconds") or 0) or (_regex_int(_DURATION_RE, blob) or 0)
    comments = _metric_from_micro_or_json(micro, blob, "commentCount", _COMMENT_RE)
    likes = _metric_from_micro_or_json(micro, blob, "likeCount", _LIKE_RE)

    if not title and views == 0 and duration == 0 and comments is None:
        return None

    channel_id = details.get("channelId") or micro.get("externalChannelId")
    thumbnails = details.get("thumbnail", {}).get("thumbnails") or []
    thumbnail = thumbnails[-1].get("url") if thumbnails else None
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return RawMetadata(
        platform=Platform.youtube,
        title=title or "Unknown title",
        creator=(details.get("author") or micro.get("ownerChannelName") or "Unknown creator").strip(),
        creator_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
        thumbnail=thumbnail,
        views=views,
        likes=likes,
        comments=comments,
        duration_seconds=duration,
        upload_date=_parse_upload_date(micro.get("publishDate") or micro.get("uploadDate")),
        description=(details.get("shortDescription") or "").strip(),
    )


def fetch_youtube_innertube_metadata(url: str) -> RawMetadata | None:
    """Fetch full YouTube metadata via the innertube player endpoint."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    for base in _INNERTUBE_ENDPOINTS:
        endpoint = f"{base}?key={_INNERTUBE_API_KEY}"
        for client in _INNERTUBE_CLIENTS:
            payload = {"context": {"client": client}, "videoId": video_id}
            try:
                with httpx.Client(timeout=30.0) as http:
                    resp = http.post(endpoint, json=payload, headers=_HEADERS)
                    if resp.status_code != 200:
                        logger.warning(
                            "YouTube innertube %s HTTP %s (%s) for %s",
                            client.get("clientName"),
                            resp.status_code,
                            base.split("/")[2],
                            video_id,
                        )
                        continue
                    data = resp.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "YouTube innertube %s failed (%s) for %s: %s",
                    client.get("clientName"),
                    base.split("/")[2],
                    video_id,
                    exc,
                )
                continue

            parsed = _parse_innertube_response(data, video_id)
            if parsed and (parsed.views or parsed.duration_seconds or parsed.comments is not None):
                logger.info(
                    "YouTube innertube (%s via %s): views=%s duration=%s for %s",
                    client.get("clientName"),
                    base.split("/")[2],
                    parsed.views,
                    parsed.duration_seconds,
                    video_id,
                )
                return parsed

    if is_youtube_cloud_host():
        proxy = fetch_frontend_proxy("innertube", video_id)
        if proxy and int(proxy.get("status") or 0) == 200:
            proxy_data = proxy.get("data")
            if isinstance(proxy_data, dict):
                parsed = _parse_innertube_response(proxy_data, video_id)
                if parsed:
                    logger.info(
                        "YouTube innertube via frontend proxy: views=%s duration=%s for %s",
                        parsed.views,
                        parsed.duration_seconds,
                        video_id,
                    )
                    return parsed

    logger.warning("YouTube innertube: all clients/endpoints failed for %s", video_id)
    return None
