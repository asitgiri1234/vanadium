"""Debug routes (metadata probes)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Query

from app.services.metadata_service import metadata_service
from app.utils.cookie_utils import cookies_configured
from app.utils.instagram_embed import fetch_instagram_fallback_metadata
from app.utils.instagram_media_api import fetch_instagram_media_info
from app.utils.instagram_page_media import extract_instagram_media_urls
from app.utils.url_utils import extract_youtube_id
from app.utils.youtube_captions import fetch_youtube_transcript_raw
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_html import fetch_youtube_html_metrics
from app.utils.youtube_innertube import fetch_youtube_innertube_metadata
from app.utils.youtube_social import _fetch_ryd, _fetch_socialcounts, fetch_youtube_social_metadata
from app.utils.youtube_web import fetch_youtube_web_metadata

router = APIRouter(prefix="/debug", tags=["debug"])

_INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"


def _raw_innertube_probe(video_id: str) -> dict:
    payload = {
        "context": {
            "client": {
                "clientName": "MWEB",
                "clientVersion": "2.20240405.01.00",
                "hl": "en",
                "gl": "US",
            }
        },
        "videoId": video_id,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
    }
    try:
        resp = httpx.post(
            f"https://youtubei.googleapis.com/youtubei/v1/player?key={_INNERTUBE_KEY}",
            json=payload,
            headers=headers,
            timeout=25.0,
        )
        data = resp.json() if resp.status_code == 200 else {}
        details = data.get("videoDetails") or {}
        return {
            "status": resp.status_code,
            "views": details.get("viewCount"),
            "duration": details.get("lengthSeconds"),
            "error": (data.get("error") or {}).get("message"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": None, "error": str(exc)[:200]}


def _raw_socialcounts_probe(video_id: str) -> dict:
    try:
        resp = httpx.get(
            f"https://api.socialcounts.org/youtube-video-live-view-count/{video_id}",
            timeout=25.0,
            headers={"Accept": "application/json", "User-Agent": "Vanadium/1.0"},
        )
        body = resp.json() if resp.status_code == 200 else {}
        counters = (body.get("counters") or {}).get("api") or {}
        return {
            "status": resp.status_code,
            "comments": counters.get("commentCount"),
            "views": counters.get("viewCount"),
            "raw": str(body)[:300],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": None, "error": str(exc)[:200]}


@router.get("/youtube-metadata")
async def debug_youtube_metadata(url: str = Query(..., description="YouTube watch URL")):
    video_id = extract_youtube_id(url) or ""
    innertube = fetch_youtube_innertube_metadata(url)
    html = fetch_youtube_html_metrics(url)
    web = fetch_youtube_web_metadata(url)
    ryd = _fetch_ryd(video_id) if video_id else None
    socialcounts = _fetch_socialcounts(video_id) if video_id else None
    social = fetch_youtube_social_metadata(url)
    transcript = fetch_youtube_transcript_raw(url)
    merged = metadata_service.fetch(url)

    return {
        "url": url,
        "cloud_host": is_youtube_cloud_host(),
        "innertube": {
            "ok": innertube is not None,
            "views": innertube.views if innertube else 0,
            "duration": innertube.duration_seconds if innertube else 0,
            "comments": innertube.comments if innertube else None,
        },
        "html_metrics": {
            "ok": html is not None,
            "views": html.views if html else 0,
            "duration": html.duration_seconds if html else 0,
            "comments": html.comments if html else None,
        },
        "web_scrape": {"ok": web is not None, "duration": web.duration_seconds if web else 0},
        "ryd": {
            "ok": ryd is not None,
            "views": ryd.views if ryd else 0,
            "likes": ryd.likes if ryd else None,
        },
        "socialcounts": {
            "ok": socialcounts is not None,
            "views": socialcounts.views if socialcounts else 0,
            "comments": socialcounts.comments if socialcounts else None,
        },
        "social_merged": {
            "ok": social is not None,
            "views": social.views if social else 0,
            "comments": social.comments if social else None,
        },
        "transcript_segments": len(transcript),
        "raw_probes": {
            "innertube_googleapis": _raw_innertube_probe(video_id) if video_id else {},
            "socialcounts": _raw_socialcounts_probe(video_id) if video_id else {},
        },
        "merged": {
            "views": merged.views,
            "likes": merged.likes,
            "comments": merged.comments,
            "duration": merged.duration_seconds,
            "title": merged.title[:80],
        },
    }


@router.get("/instagram-metadata")
async def debug_instagram_metadata(url: str = Query(..., description="Instagram reel URL")):
    merged = metadata_service.fetch(url)
    fallback = fetch_instagram_fallback_metadata(url)
    media_info = fetch_instagram_media_info(url)
    scraped = extract_instagram_media_urls(url)
    return {
        "url": url,
        "cloud_host": is_youtube_cloud_host(),
        "cookies_configured": cookies_configured(),
        "media_api": media_info,
        "page_scrape": {
            "like_count": scraped.get("like_count"),
            "comment_count": scraped.get("comment_count"),
            "video_urls": len(scraped.get("video_urls") or []),
        },
        "fallback": {
            "ok": fallback is not None,
            "title": fallback.title if fallback else None,
            "creator": fallback.creator if fallback else None,
            "thumbnail": bool(fallback.thumbnail) if fallback else False,
            "likes": fallback.likes if fallback else None,
            "comments": fallback.comments if fallback else None,
        },
        "merged": {
            "title": merged.title,
            "creator": merged.creator,
            "follower_count": merged.follower_count,
            "views": merged.views,
            "likes": merged.likes,
            "comments": merged.comments,
            "thumbnail": bool(merged.thumbnail),
            "ig_video_urls": len((merged.raw or {}).get("ig_video_urls") or [])
            if isinstance(merged.raw, dict)
            else 0,
        },
    }
