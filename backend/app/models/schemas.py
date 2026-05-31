"""Pydantic models: API requests/responses and internal domain objects.

These types are the single source of truth for data shapes shared across the
ingestion, RAG, and API layers.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

VideoSlot = Literal["A", "B"]


class Platform(str, Enum):
    youtube = "youtube"
    instagram = "instagram"
    unknown = "unknown"


# --------------------------------------------------------------------------- #
# Domain objects
# --------------------------------------------------------------------------- #
class VideoMetadata(BaseModel):
    """Everything we know about a single video after ingestion."""

    video_id: VideoSlot
    platform: Platform
    url: str

    title: str = "Unknown title"
    creator: str = "Unknown creator"
    follower_count: int = 0

    thumbnail: Optional[str] = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    duration_seconds: int = 0
    upload_date: Optional[str] = None  # ISO date string
    hashtags: list[str] = Field(default_factory=list)

    engagement_rate: float = 0.0
    transcript_available: bool = False
    chunk_count: int = 0

    def to_card_text(self) -> str:
        """Render an embeddable natural-language summary of this video's metadata.

        This is the document stored (and embedded) as the video's metadata
        record in the vector store, so questions like "who created Video B and
        what is their follower count?" can retrieve it.
        """
        tags = ", ".join(self.hashtags) if self.hashtags else "none"
        return (
            f"Video {self.video_id} ({self.platform.value}). "
            f"Title: {self.title}. "
            f"Creator: {self.creator} with {self.follower_count:,} followers. "
            f"Views: {self.views:,}. Likes: {self.likes:,}. "
            f"Comments: {self.comments:,}. "
            f"Engagement rate: {self.engagement_rate}%. "
            f"Duration: {self.duration_seconds} seconds. "
            f"Uploaded: {self.upload_date or 'unknown'}. "
            f"Hashtags: {tags}."
        )


class ChunkMetadata(BaseModel):
    """Metadata attached to every transcript chunk in the vector store.

    Matches the product-required shape exactly.
    """

    analysis_id: str
    video_id: VideoSlot
    chunk_index: int
    timestamp: str  # e.g. "00:12-00:20"
    source_platform: Platform


class TranscriptSegment(BaseModel):
    """A raw, time-coded transcript segment from an extractor."""

    text: str
    start: float  # seconds
    duration: float  # seconds


class TranscriptChunk(BaseModel):
    """A cleaned, windowed chunk ready for embedding + indexing."""

    id: str
    text: str
    metadata: ChunkMetadata


class Citation(BaseModel):
    """A structured source reference returned with a chat answer."""

    video_id: VideoSlot
    chunk_index: int
    timestamp: str
    source_platform: Platform
    snippet: str = ""


class ComparisonInsights(BaseModel):
    """Strategist-grade comparison summary surfaced on the dashboard."""

    winner: Optional[VideoSlot] = None
    engagement_delta: float = 0.0
    headline_insights: list[str] = Field(default_factory=list)
    hook_a: str = ""
    hook_b: str = ""
    cta_a: bool = False
    cta_b: bool = False
    strategist_summary: str = ""  # LLM narrative comparison (when OpenAI configured)
    recommendations: list[str] = Field(default_factory=list)  # actionable tips
    ai_pending: bool = False  # True while background LLM comparison is running
    ai_error: str = ""  # Set when background LLM comparison fails


class AnalysisSnapshot(BaseModel):
    """The full result of an ingest, used by the dashboard and RAG context."""

    analysis_id: str
    videos: dict[VideoSlot, VideoMetadata]
    comparison: ComparisonInsights


# --------------------------------------------------------------------------- #
# API requests / responses
# --------------------------------------------------------------------------- #
class IngestRequest(BaseModel):
    video_a_url: str = Field(..., min_length=4)
    video_b_url: str = Field(..., min_length=4)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    llm_provider: str = "openai"
    llm_configured: bool = False
    openai_configured: bool = False
    groq_configured: bool = False
    whisper_enabled: bool = False
    visual_enabled: bool = False


class TranscriptLine(BaseModel):
    start: float  # seconds
    timestamp: str  # MM:SS
    text: str


class VideoTranscript(BaseModel):
    video_id: VideoSlot
    platform: Platform
    available: bool
    segments: list[TranscriptLine] = Field(default_factory=list)


class TranscriptResponse(BaseModel):
    analysis_id: str
    whisper_enabled: bool = False
    transcripts: dict[VideoSlot, VideoTranscript]


class VisualFrame(BaseModel):
    start: float  # seconds
    timestamp: str  # MM:SS
    ocr_text: str = ""  # on-screen text extracted via OCR


class VideoVisual(BaseModel):
    video_id: VideoSlot
    platform: Platform
    available: bool = False
    frames: list[VisualFrame] = Field(default_factory=list)
    visual_summary: str = ""  # scene description from the vision LLM (if enabled)
    on_screen_text: str = ""  # text overlays read by the vision LLM


class VisualResponse(BaseModel):
    analysis_id: str
    enabled: bool = False  # ENABLE_VISUAL
    vision_enabled: bool = False  # OpenAI vision available for scene descriptions
    visuals: dict[VideoSlot, VideoVisual]


class ChatRequest(BaseModel):
    analysis_id: str
    message: str = Field(..., min_length=1)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ErrorResponse(BaseModel):
    detail: str
