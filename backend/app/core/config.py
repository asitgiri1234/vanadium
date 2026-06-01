"""Application configuration.

All runtime settings are loaded from environment variables (or a local ``.env``
file) via pydantic-settings. Keeping configuration in one typed object means
services never read ``os.environ`` directly and stay easy to test.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM provider: "openai" or "groq"
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", alias="EMBEDDING_MODEL"
    )

    # Groq (OpenAI-compatible API — fast text + Llama 4 Scout for vision)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(
        default="llama-3.3-70b-versatile", alias="GROQ_MODEL"
    )
    groq_vision_model: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        alias="GROQ_VISION_MODEL",
    )

    # Vector store
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    chroma_collection: str = Field(default="vanadium_chunks", alias="CHROMA_COLLECTION")
    analysis_persist_dir: str = Field(
        default="./data/analyses", alias="ANALYSIS_PERSIST_DIR"
    )

    # Chunking
    chunk_size: int = Field(default=600, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")

    # Retrieval / memory
    retrieval_top_k: int = Field(default=4, alias="RETRIEVAL_TOP_K")
    memory_max_turns: int = Field(default=8, alias="MEMORY_MAX_TURNS")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Instagram transcription
    # Provider: auto (Groq API if key set, else local), groq, local
    whisper_provider: str = Field(default="auto", alias="WHISPER_PROVIDER")
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")
    groq_whisper_model: str = Field(
        default="whisper-large-v3-turbo", alias="GROQ_WHISPER_MODEL"
    )
    whisper_max_audio_seconds: int = Field(
        default=900, alias="WHISPER_MAX_AUDIO_SECONDS"
    )
    enable_whisper: bool = Field(default=False, alias="ENABLE_WHISPER")

    # Instagram authentication for yt-dlp (unlocks views/play counts + private
    # data on the authenticated API path). Provide ONE of these:
    #   - a Netscape-format cookies.txt exported from a logged-in session, OR
    #   - a browser name to read cookies from (chrome|edge|firefox|brave|...).
    instagram_cookies_file: str = Field(default="", alias="INSTAGRAM_COOKIES_FILE")
    cookies_from_browser: str = Field(default="", alias="COOKIES_FROM_BROWSER")

    # Optional YouTube Data API key — reliable views/likes on cloud hosts when
    # yt-dlp and watch-page scraping are blocked. Free tier: 10k units/day.
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")

    # Optional Supadata key — cloud transcript fallback when YouTube blocks captions.
    supadata_api_key: str = Field(default="", alias="SUPADATA_API_KEY")

    # SerpApi — reliable YouTube transcripts from datacenter IPs (serpapi.com).
    serp_api_key: str = Field(default="", alias="SERP_API_KEY")

    # Apify — Instagram transcripts (crawlerbros/instagram-transcript-scraper).
    apify_api_key: str = Field(default="", alias="APIFY_API_KEY")

    # Vercel frontend URL for YouTube proxy routes when datacenter APIs return 403.
    frontend_proxy_url: str = Field(default="", alias="FRONTEND_PROXY_URL")

    # Visual understanding (vision LLM reads scene + on-screen text from frames).
    enable_visual: bool = Field(default=False, alias="ENABLE_VISUAL")
    enable_ocr: bool = Field(default=False, alias="ENABLE_OCR")
    tesseract_cmd: str = Field(default="", alias="TESSERACT_CMD")
    visual_max_frames: int = Field(default=4, alias="VISUAL_MAX_FRAMES")
    visual_max_height: int = Field(default=480, alias="VISUAL_MAX_HEIGHT")

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.strip())

    @property
    def llm_configured(self) -> bool:
        """True when the active LLM provider has an API key."""
        if self.llm_provider.lower() == "groq":
            return self.groq_configured
        return self.openai_configured

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
