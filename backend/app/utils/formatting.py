"""Display helpers for optional engagement counts."""

from __future__ import annotations


def fmt_count(value: int | None) -> str:
    """Format an integer metric for prompts/UI; unavailable → N/A."""
    if value is None:
        return "N/A"
    return f"{value:,}"
