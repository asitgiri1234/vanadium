"""Raw metadata extracted from external sources before schema mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.schemas import Platform


@dataclass
class RawMetadata:
    platform: Platform
    title: str = "Unknown title"
    creator: str = "Unknown creator"
    creator_url: str | None = None
    follower_count: int | None = None
    thumbnail: Optional[str] = None
    views: int = 0
    likes: int | None = None
    comments: int | None = None
    duration_seconds: int = 0
    upload_date: Optional[str] = None
    hashtags: list[str] = field(default_factory=list)
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
