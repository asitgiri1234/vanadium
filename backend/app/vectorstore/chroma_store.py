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
from app.models.schemas import (
    Citation,
    Platform,
    TranscriptChunk,
    VideoMetadata,
    VideoSlot,
)

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
                "record_type": "transcript",
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
        logger.info("Upserted %d transcript chunks", len(chunks))

    def upsert_metadata(
        self,
        analysis_id: str,
        videos: dict[VideoSlot, VideoMetadata],
        embeddings: list[list[float]],
    ) -> None:
        """Store one metadata record per video in the same collection.

        ``embeddings`` must align with ``videos`` ordered by slot (A then B).
        The embeddable document is the video's metadata card; the raw numeric
        fields are kept as scalar Chroma metadata (``record_type="metadata"``)
        so they stay queryable.
        """
        if not videos:
            return
        slots = sorted(videos.keys())
        collection = self._get_collection()
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for slot in slots:
            v = videos[slot]
            ids.append(f"{analysis_id}:{slot}:meta")
            documents.append(v.to_card_text())
            metadatas.append(
                {
                    "record_type": "metadata",
                    "analysis_id": analysis_id,
                    "video_id": slot,
                    "source_platform": v.platform.value,
                    "title": v.title,
                    "creator": v.creator,
                    "follower_count": v.follower_count,
                    "views": v.views,
                    "likes": v.likes,
                    "comments": v.comments,
                    "duration_seconds": v.duration_seconds,
                    "upload_date": v.upload_date or "",
                    "engagement_rate": v.engagement_rate,
                    "hashtags": ", ".join(v.hashtags),
                }
            )
        collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )
        logger.info("Upserted %d metadata records", len(ids))

    def upsert_visual(
        self,
        analysis_id: str,
        video_id: VideoSlot,
        platform: Platform,
        text: str,
        embedding: list[float],
    ) -> None:
        """Store a video's visual analysis (OCR + scene summary) as a record."""
        if not text.strip():
            return
        collection = self._get_collection()
        collection.upsert(
            ids=[f"{analysis_id}:{video_id}:visual"],
            embeddings=[embedding],
            documents=[text],
            metadatas=[
                {
                    "record_type": "visual",
                    "analysis_id": analysis_id,
                    "video_id": video_id,
                    "source_platform": platform.value,
                }
            ],
        )
        logger.info("Upserted visual record for video %s", video_id)

    def get_metadata_records(self, analysis_id: str) -> list[dict[str, Any]]:
        """Return the stored metadata records for an analysis (for inspection)."""
        collection = self._get_collection()
        result = collection.get(
            where={
                "$and": [
                    {"analysis_id": analysis_id},
                    {"record_type": "metadata"},
                ]
            },
            include=["documents", "metadatas"],
        )
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        return [{"document": d, "metadata": m} for d, m in zip(docs, metas)]

    def query(
        self,
        query_embedding: list[float],
        analysis_id: str,
        video_id: VideoSlot | None = None,
        top_k: int = 4,
    ) -> list[Citation]:
        """Return citations for the most relevant chunks within an analysis."""
        collection = self._get_collection()

        conditions: list[dict[str, Any]] = [
            {"analysis_id": analysis_id},
            {"record_type": "transcript"},
        ]
        if video_id is not None:
            conditions.append({"video_id": video_id})
        where: dict[str, Any] = {"$and": conditions}

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
