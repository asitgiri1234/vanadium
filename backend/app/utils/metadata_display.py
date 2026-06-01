"""Human-readable metadata for LLM prompts (unknown ≠ zero)."""

from __future__ import annotations


def fmt_followers(count: int | None, platform: str) -> str:
    if count is None or count <= 0:
        if platform == "instagram":
            return "unknown (Instagram often hides follower counts without login)"
        return "unknown"
    return f"{count:,}"


def fmt_views(count: int | None, platform: str) -> str:
    if count is None or count <= 0:
        if platform == "instagram":
            return "hidden/unavailable (Instagram often does not expose reel view counts)"
        return "unknown"
    return f"{count:,}"


def fmt_engagement(rate: float, views: int | None, platform: str) -> str:
    if views is None or views <= 0:
        if platform == "instagram":
            return "unavailable (views hidden — not zero engagement)"
        return "unavailable"
    return f"{rate}%"


def followers_known(count: int | None) -> bool:
    return count is not None and count > 0


def coalesce_count(a: int | None, b: int | None) -> int | None:
    """Prefer the first known positive metric; treat 0 as unknown."""
    if a is not None and a > 0:
        return a
    if b is not None and b > 0:
        return b
    return None
