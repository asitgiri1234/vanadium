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

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", alias="EMBEDDING_MODEL"
    )

    # Vector store
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    chroma_collection: str = Field(default="vanadium_chunks", alias="CHROMA_COLLECTION")

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
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")
    enable_whisper: bool = Field(default=False, alias="ENABLE_WHISPER")

    # Instagram authentication for yt-dlp (unlocks views/play counts + private
    # data on the authenticated API path). Provide ONE of these:
    #   - a Netscape-format cookies.txt exported from a logged-in session, OR
    #   - a browser name to read cookies from (chrome|edge|firefox|brave|...).
    instagram_cookies_file: str = Field(default="", alias="INSTAGRAM_COOKIES_FILE")
    cookies_from_browser: str = Field(default="", alias="COOKIES_FROM_BROWSER")

    # Visual understanding (frame OCR + optional vision-LLM scene description).
    enable_visual: bool = Field(default=False, alias="ENABLE_VISUAL")
    tesseract_cmd: str = Field(default="", alias="TESSERACT_CMD")
    visual_max_frames: int = Field(default=8, alias="VISUAL_MAX_FRAMES")
    visual_max_height: int = Field(default=720, alias="VISUAL_MAX_HEIGHT")

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
