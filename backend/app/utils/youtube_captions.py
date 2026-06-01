"""YouTube caption / transcript extraction with cloud fallbacks."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.url_utils import extract_youtube_id
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_proxy import fetch_frontend_proxy
from app.utils.youtube_serpapi import fetch_youtube_transcript_serpapi

logger = get_logger(__name__)

_WATCH_UA = (
    "Mozilla/5.0 (Linux; Android 10; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
_CONSENT_COOKIE = {"CONSENT": "YES+cb.20210328-17-p0.en+FX+667"}

_INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
_INNERTUBE_CLIENTS = (
    {"clientName": "ANDROID", "clientVersion": "20.10.38", "hl": "en", "gl": "US"},
    {"clientName": "MWEB", "clientVersion": "2.20240405.01.00", "hl": "en", "gl": "US"},
    {"clientName": "WEB", "clientVersion": "2.20240405.00.00", "hl": "en", "gl": "US"},
    {"clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER", "clientVersion": "2.0", "hl": "en", "gl": "US"},
)


def _extract_json_array(html: str, marker: str) -> list[dict[str, Any]] | None:
    idx = html.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    while start < len(html) and html[start] in " \t\n\r":
        start += 1
    if start >= len(html) or html[start] != "[":
        return None
    depth = 0
    for i in range(start, len(html)):
        ch = html[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(html[start : i + 1])
                    return parsed if isinstance(parsed, list) else None
                except json.JSONDecodeError:
                    return None
    return None


def _parse_json3_events(raw: bytes) -> list[dict]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []

    segments: list[dict] = []
    for event in payload.get("events") or []:
        start_ms = float(event.get("tStartMs") or 0)
        start = start_ms / 1000.0
        parts: list[str] = []
        for seg in event.get("segs") or []:
            text = (seg.get("utf8") or "").strip()
            if text and text != "\n":
                parts.append(text)
        if not parts:
            continue
        text = " ".join(parts).strip()
        if text:
            segments.append({"text": text, "start": start, "duration": 0.0})
    return segments


def _parse_vtt(vtt: str) -> list[dict]:
    segments: list[dict] = []
    start_sec = 0.0
    block: list[str] = []

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
                {"text": " ".join(block), "start": start_sec, "duration": 0.0}
            )
            block = []

    merged: list[dict] = []
    for seg in segments:
        if merged and merged[-1]["text"] == seg["text"]:
            continue
        merged.append(seg)
    return merged


def _fetch_caption_url(url: str) -> list[dict]:
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            headers = {"User-Agent": _WATCH_UA, "Accept-Language": "en-US,en;q=0.9"}
            for suffix in ("&fmt=json3", "&fmt=vtt", "&fmt=srv3", ""):
                resp = client.get(url + suffix, headers=headers)
                if resp.status_code != 200 or not resp.content:
                    continue
                text = resp.text
                if "json3" in suffix or text.strip().startswith("{"):
                    parsed = _parse_json3_events(resp.content)
                    if parsed:
                        return parsed
                if "vtt" in suffix or text.strip().startswith("WEBVTT"):
                    parsed = _parse_vtt(text)
                    if parsed:
                        return parsed
                if "<text" in text:
                    parsed = _parse_xml_captions(text)
                    if parsed:
                        return parsed
    except Exception as exc:  # noqa: BLE001
        logger.warning("Caption download failed for %s: %s", url[:80], exc)
    return []


def _parse_xml_captions(raw: str) -> list[dict]:
    """Parse YouTube timedtext XML (<text start=...>)."""
    segments: list[dict] = []
    for match in re.finditer(
        r'<text start="([^"]+)"[^>]*>([\s\S]*?)</text>', raw
    ):
        try:
            start = float(match.group(1))
        except ValueError:
            start = 0.0
        text = (
            match.group(2)
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&#39;", "'")
            .replace("&quot;", '"')
            .replace("\n", " ")
            .strip()
        )
        if text:
            segments.append({"text": text, "start": start, "duration": 0.0})
    return segments


def _fetch_from_innertube(video_id: str) -> list[dict]:
    """Caption tracks via youtubei.googleapis.com — works on Render datacenter IPs."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _WATCH_UA,
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
    }
    for client in _INNERTUBE_CLIENTS:
        try:
            with httpx.Client(timeout=35.0, follow_redirects=True) as http:
                resp = http.post(
                    f"https://youtubei.googleapis.com/youtubei/v1/player?key={_INNERTUBE_KEY}",
                    json={"context": {"client": client}, "videoId": video_id},
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue
                player = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Innertube player failed for %s: %s", video_id, exc)
            continue

        tracks = (
            player.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks")
            or []
        )
        if not tracks:
            continue

        def lang_score(code: str) -> int:
            if code.startswith("en"):
                return 0
            if code.startswith("a.en"):
                return 1
            return 2

        sorted_tracks = sorted(
            tracks,
            key=lambda t: lang_score(str(t.get("languageCode") or "")),
        )
        for track in sorted_tracks:
            base = track.get("baseUrl") or ""
            if not base:
                continue
            if base.startswith("/"):
                base = urljoin("https://www.youtube.com", base)
            segments = _fetch_caption_url(base)
            if segments:
                logger.info(
                    "YouTube captions from innertube (%s) for %s: %d segments",
                    track.get("languageCode"),
                    video_id,
                    len(segments),
                )
                return segments
    return []


def _fetch_from_watch_html(video_id: str) -> list[dict]:
    watch_urls = [
        f"https://m.youtube.com/watch?v={video_id}",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    for watch_url in watch_urls:
        try:
            with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                resp = client.get(
                    watch_url,
                    headers={"User-Agent": _WATCH_UA, "Accept-Language": "en-US,en;q=0.9"},
                    cookies=_CONSENT_COOKIE,
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Watch page fetch failed for %s: %s", watch_url, exc)
            continue

        tracks = _extract_json_array(html, '"captionTracks":')
        if not tracks:
            continue

        for track in tracks:
            lang = str(track.get("languageCode") or "")
            if lang and not lang.startswith("en"):
                continue
            base = track.get("baseUrl") or ""
            if not base:
                continue
            if base.startswith("/"):
                base = urljoin("https://www.youtube.com", base)
            segments = _fetch_caption_url(base)
            if segments:
                logger.info(
                    "YouTube captions from watch HTML (%s) for %s: %d segments",
                    lang,
                    video_id,
                    len(segments),
                )
                return segments

    return []


def _fetch_from_transcript_api(video_id: str) -> list[dict]:
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


def _fetch_from_transcript_api_list(video_id: str) -> list[dict]:
    """Use transcript API track URLs (includes signed timedtext params)."""
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("YouTube transcript list failed for %s: %s", video_id, exc)
        return []

    for transcript in transcript_list:
        lang = getattr(transcript, "language_code", "") or ""
        if lang and not str(lang).startswith("en"):
            continue
        url = getattr(transcript, "_url", None)
        if not url:
            continue
        segments = _fetch_caption_url(url)
        if segments:
            logger.info(
                "YouTube captions from transcript API track for %s: %d segments",
                video_id,
                len(segments),
            )
            return segments
    return []


def _fetch_from_supadata(video_id: str) -> list[dict]:
    api_key = settings.supadata_api_key.strip()
    if not api_key:
        return []
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.get(
                "https://api.supadata.ai/v1/youtube/transcript",
                params={"videoId": video_id},
                headers={"x-api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supadata transcript failed for %s: %s", video_id, exc)
        return []

    segments: list[dict] = []
    for item in data.get("content") or data.get("transcript") or []:
        if isinstance(item, dict):
            text = (item.get("text") or item.get("content") or "").strip()
            start = float(item.get("offset") or item.get("start") or 0.0)
            duration = float(item.get("duration") or 0.0)
        else:
            text = str(item).strip()
            start = 0.0
            duration = 0.0
        if text:
            segments.append({"text": text, "start": start, "duration": duration})
    return segments


def fetch_youtube_transcript_raw(url: str) -> list[dict]:
    """Best-effort transcript fetch using multiple providers."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return []

    cloud = is_youtube_cloud_host()

    if settings.serp_api_key.strip():
        segments = fetch_youtube_transcript_serpapi(video_id)
        if segments:
            return segments

    # Innertube via googleapis.com is the most reliable free path on Render.
    segments = _fetch_from_innertube(video_id)
    if segments:
        return segments

    if cloud and settings.supadata_api_key.strip():
        segments = _fetch_from_supadata(video_id)
        if segments:
            return segments

    if cloud:
        proxy = fetch_frontend_proxy("transcript", video_id)
        if proxy:
            segments = proxy.get("segments") or []
            if isinstance(segments, list) and segments:
                parsed = [s for s in segments if isinstance(s, dict)]
                if parsed:
                    logger.info(
                        "YouTube captions from Vercel proxy for %s: %d segments",
                        video_id,
                        len(parsed),
                    )
                    return parsed

    for fetcher in (
        _fetch_from_transcript_api,
        _fetch_from_transcript_api_list,
        _fetch_from_watch_html,
        _fetch_from_supadata,
    ):
        segments = fetcher(video_id)
        if segments:
            return segments

    return []
