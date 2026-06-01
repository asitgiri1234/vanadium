"""Load Netscape cookies.txt for authenticated HTTP requests."""

from __future__ import annotations

import os
import re
from http.cookiejar import MozillaCookieJar
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_COOKIE_LINE = re.compile(
    r"^\.?(?P<domain>[^\s]+)\s+"
    r"(?P<flag>\w+)\s+"
    r"(?P<path>[^\s]+)\s+"
    r"(?P<secure>\w+)\s+"
    r"(?P<expiry>\d+)\s+"
    r"(?P<name>[^\s]+)\s+"
    r"(?P<value>.+)$"
)


def _load_jar(cookie_file: str) -> MozillaCookieJar | None:
    try:
        jar = MozillaCookieJar(cookie_file)
        jar.load(ignore_discard=True, ignore_expires=True)
        if len(jar):
            return jar
    except Exception as exc:  # noqa: BLE001
        logger.warning("Strict cookie parse failed for %s: %s", cookie_file, exc)

    # Render Secret Files sometimes replace tabs with spaces — parse leniently.
    jar = MozillaCookieJar()
    try:
        with open(cookie_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = _COOKIE_LINE.match(line)
                if not match:
                    continue
                parts = match.groupdict()
                domain = parts["domain"]
                if not domain.startswith("."):
                    domain = f".{domain}"
                jar.set(
                    parts["name"],
                    parts["value"],
                    domain=domain,
                    path=parts["path"] or "/",
                    secure=parts["secure"].upper() == "TRUE",
                    rest={"HttpOnly": None},
                    expires=int(parts["expiry"]) if parts["expiry"] != "0" else None,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Lenient cookie parse failed for %s: %s", cookie_file, exc)
        return None

    return jar if len(jar) else None


def cookies_configured() -> bool:
    path = settings.instagram_cookies_file.strip()
    return bool(path and os.path.exists(path))


def cookie_header_for_url(url: str) -> dict[str, str]:
    """Return a Cookie header dict for ``url`` when a cookies file is configured."""
    cookie_file = settings.instagram_cookies_file.strip()
    if not cookie_file:
        return {}
    if not os.path.exists(cookie_file):
        logger.warning("Instagram cookies file not found: %s", cookie_file)
        return {}

    jar = _load_jar(cookie_file)
    if not jar:
        logger.warning("Instagram cookies file loaded 0 cookies from %s", cookie_file)
        return {}

    host = urlparse(url).hostname or ""
    parts: list[str] = []
    for cookie in jar:
        domain = cookie.domain.lstrip(".")
        if host == domain or host.endswith(f".{domain}"):
            parts.append(f"{cookie.name}={cookie.value}")

    if not parts:
        logger.debug("No cookies matched host %s from %s", host, cookie_file)
        return {}
    return {"Cookie": "; ".join(parts)}
