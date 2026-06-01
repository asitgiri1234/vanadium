"""Debug routes (metadata probes)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.metadata_service import metadata_service
from app.utils.youtube_captions import fetch_youtube_transcript_raw
from app.utils.youtube_html import fetch_youtube_html_metrics
from app.utils.youtube_innertube import fetch_youtube_innertube_metadata
from app.utils.youtube_cloud import is_youtube_cloud_host
from app.utils.youtube_social import fetch_youtube_social_metadata
from app.utils.youtube_web import fetch_youtube_web_metadata

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/youtube-metadata")
async def debug_youtube_metadata(url: str = Query(..., description="YouTube watch URL")):
    innertube = fetch_youtube_innertube_metadata(url)
    html = fetch_youtube_html_metrics(url)
    web = fetch_youtube_web_metadata(url)
    social = fetch_youtube_social_metadata(url)
    transcript = fetch_youtube_transcript_raw(url)
    merged = metadata_service.fetch(url)

    return {
        "url": url,
        "cloud_host": is_youtube_cloud_host(),
        "innertube": {"ok": innertube is not None, "views": innertube.views if innertube else 0},
        "html_metrics": {
            "ok": html is not None,
            "views": html.views if html else 0,
            "duration": html.duration_seconds if html else 0,
            "comments": html.comments if html else None,
        },
        "web_scrape": {"ok": web is not None, "duration": web.duration_seconds if web else 0},
        "social": {
            "ok": social is not None,
            "views": social.views if social else 0,
            "comments": social.comments if social else None,
        },
        "transcript_segments": len(transcript),
        "merged": {
            "views": merged.views,
            "likes": merged.likes,
            "comments": merged.comments,
            "duration": merged.duration_seconds,
            "title": merged.title[:80],
        },
    }
