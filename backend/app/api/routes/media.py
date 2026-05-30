"""Media proxy.

Instagram's CDN serves images only with a valid ``Referer`` and blocks
cross-origin hotlinking, so a browser ``<img>`` pointing straight at a reel
thumbnail gets a 403. This endpoint fetches the image server-side (with the
right headers) and streams it back, so thumbnails render in the dashboard.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["media"])

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


@router.get("/thumbnail")
async def thumbnail(url: str = Query(..., min_length=8)) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http(s) URLs are allowed.")

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=_BROWSER_HEADERS)
    except httpx.HTTPError as exc:
        logger.warning("Thumbnail proxy failed for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail="Failed to fetch image.") from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}.")

    content_type = resp.headers.get("content-type", "image/jpeg")
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
