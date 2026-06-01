"""Load Netscape cookies.txt for authenticated HTTP requests."""

from __future__ import annotations

from http.cookiejar import MozillaCookieJar
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def cookie_header_for_url(url: str) -> dict[str, str]:
    """Return a Cookie header dict for ``url`` when a cookies file is configured."""
    cookie_file = settings.instagram_cookies_file.strip()
    if not cookie_file:
        return {}

    try:
        jar = MozillaCookieJar(cookie_file)
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not load cookies file %s: %s", cookie_file, exc)
        return {}

    host = urlparse(url).hostname or ""
    parts: list[str] = []
    for cookie in jar:
        domain = cookie.domain.lstrip(".")
        if host == domain or host.endswith(f".{domain}"):
            parts.append(f"{cookie.name}={cookie.value}")

    if not parts:
        return {}
    return {"Cookie": "; ".join(parts)}
