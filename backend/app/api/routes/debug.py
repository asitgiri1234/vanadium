"""Debug routes (metadata probes) — remove or protect in production if needed."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.metadata_service import metadata_service
from app.utils.youtube_innertube import fetch_youtube_innertube_metadata
from app.utils.youtube_web import fetch_youtube_web_metadata

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/youtube-metadata")
async def debug_youtube_metadata(url: str = Query(..., description="YouTube watch URL")):
    """Probe which YouTube metadata sources succeed (for production diagnostics)."""
    innertube = fetch_youtube_innertube_metadata(url)
    web = fetch_youtube_web_metadata(url)
    merged = metadata_service.fetch(url)

    return {
        "url": url,
        "innertube": {
            "ok": innertube is not None,
            "views": innertube.views if innertube else 0,
            "likes": innertube.likes if innertube else None,
            "duration": innertube.duration_seconds if innertube else 0,
            "title": (innertube.title[:80] if innertube else None),
        },
        "web_scrape": {
            "ok": web is not None,
            "views": web.views if web else 0,
            "duration": web.duration_seconds if web else 0,
        },
        "merged": {
            "views": merged.views,
            "likes": merged.likes,
            "duration": merged.duration_seconds,
            "title": merged.title[:80],
        },
    }
