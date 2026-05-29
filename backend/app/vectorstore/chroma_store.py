"""ChromaDB wrapper.

A thin, typed facade over a persistent Chroma collection. We pass precomputed
embeddings (from ``embedding_service``) so the embedder is the single source of
truth and the collection stays consistent across online/offline modes.

All chunks for every analysis live in one collection and are partitioned
logically by the ``analysis_id`` metadata field.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Citation, Platform, TranscriptChunk, VideoSlot

logger = get_logger(__name__)


class ChromaStore:
    def __init__(self) -> None:
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Chroma collection ready: %s", settings.chroma_collection)
        return self._collection

    # ----------------------------------------------------------------- #
    def upsert_chunks(
        self, chunks: list[TranscriptChunk], embeddings: list[list[float]]
    ) -> None:
        if not chunks:
            return
        collection = self._get_collection()
        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas: list[dict[str, Any]] = [
            {
                "analysis_id": c.metadata.analysis_id,
                "video_id": c.metadata.video_id,
                "chunk_index": c.metadata.chunk_index,
                "timestamp": c.metadata.timestamp,
                "source_platform": c.metadata.source_platform.value,
            }
            for c in chunks
        ]
        collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )
        logger.info("Upserted %d chunks", len(chunks))

    def query(
        self,
        query_embedding: list[float],
        analysis_id: str,
        video_id: VideoSlot | None = None,
        top_k: int = 4,
    ) -> list[Citation]:
        """Return citations for the most relevant chunks within an analysis."""
        collection = self._get_collection()

        where: dict[str, Any] = {"analysis_id": analysis_id}
        if video_id is not None:
            where = {
                "$and": [
                    {"analysis_id": analysis_id},
                    {"video_id": video_id},
                ]
            }

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas"],
        )

        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        citations: list[Citation] = []
        for doc, meta in zip(docs, metas):
            citations.append(
                Citation(
                    video_id=meta.get("video_id", "A"),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    timestamp=meta.get("timestamp", "00:00-00:00"),
                    source_platform=Platform(meta.get("source_platform", "unknown")),
                    snippet=doc or "",
                )
            )
        return citations

    def delete_analysis(self, analysis_id: str) -> None:
        try:
            self._get_collection().delete(where={"analysis_id": analysis_id})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete analysis %s: %s", analysis_id, exc)


chroma_store = ChromaStore()
