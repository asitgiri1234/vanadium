"""Embedding service.

Wraps OpenAI ``text-embedding-3-small`` (via langchain-openai). When no API key
is configured it falls back to a deterministic, dependency-free hashing
embedder so the full ingest → index → retrieve flow still works offline.

Both embedders emit vectors of the same fixed dimension so a persisted Chroma
collection stays consistent regardless of mode.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# text-embedding-3-small dimensionality; the fallback matches it.
EMBED_DIM = 1536
_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")


class EmbeddingService:
    def __init__(self) -> None:
        self._client = None
        if settings.openai_configured:
            try:
                from langchain_openai import OpenAIEmbeddings

                self._client = OpenAIEmbeddings(
                    model=settings.embedding_model,
                    api_key=settings.openai_api_key,
                )
                logger.info("Embeddings: OpenAI %s", settings.embedding_model)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI embeddings unavailable (%s); using fallback", exc)
        if self._client is None:
            logger.info("Embeddings: local deterministic fallback (dim=%d)", EMBED_DIM)

    @property
    def using_openai(self) -> bool:
        return self._client is not None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client is not None:
            try:
                return self._client.embed_documents(texts)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI embed_documents failed (%s); using fallback", exc)
        return [self._hash_embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        if self._client is not None:
            try:
                return self._client.embed_query(text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI embed_query failed (%s); using fallback", exc)
        return self._hash_embed(text)

    # ----------------------------------------------------------------- #
    # Deterministic offline embedder: hashed bag-of-words, L2-normalised.
    # ----------------------------------------------------------------- #
    @staticmethod
    def _hash_embed(text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        tokens = _TOKEN_RE.findall((text or "").lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % EMBED_DIM
            sign = 1.0 if (h >> 7) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


embedding_service = EmbeddingService()
