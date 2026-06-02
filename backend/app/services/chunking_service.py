"""Chunking service.

Turns raw, time-coded transcript segments into cleaned, overlapping chunks that
carry the exact metadata required by the product spec
(``analysis_id``, ``video_id``, ``chunk_index``, ``timestamp``,
``source_platform``).

Chunks are built by accumulating segments up to a target character size with a
character-based overlap, preserving the start/end timestamps of the window.
"""

from __future__ import annotations

from app.core.config import settings
from app.models.schemas import (
    ChunkMetadata,
    Platform,
    TranscriptChunk,
    TranscriptSegment,
    VideoSlot,
)
from app.utils.text import clean_text, timestamp_range


class ChunkingService:
    def __init__(self, chunk_size: int | None = None, overlap: int | None = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.overlap = overlap or settings.chunk_overlap
        # Keep overlap around 10-15% of chunk size to reduce duplicate embeddings
        # while maintaining semantic continuity across chunk boundaries.

    def chunk(
        self,
        segments: list[TranscriptSegment],
        analysis_id: str,
        video_id: VideoSlot,
        platform: Platform,
    ) -> list[TranscriptChunk]:
        if not segments:
            return []

        chunks: list[TranscriptChunk] = []
        window: list[TranscriptSegment] = []
        window_len = 0
        chunk_index = 0

        for seg in segments:
            seg_text = clean_text(seg.text)
            if not seg_text:
                continue
            window.append(seg)
            window_len += len(seg_text) + 1

            if window_len >= self.chunk_size:
                chunks.append(
                    self._build_chunk(
                        window, analysis_id, video_id, platform, chunk_index
                    )
                )
                chunk_index += 1
                window, window_len = self._carry_overlap(window)

        # Flush any trailing window that has meaningful content.
        if window and self._window_text(window).strip():
            chunks.append(
                self._build_chunk(window, analysis_id, video_id, platform, chunk_index)
            )

        return chunks

    # ----------------------------------------------------------------- #
    def _carry_overlap(
        self, window: list[TranscriptSegment]
    ) -> tuple[list[TranscriptSegment], int]:
        """Keep trailing segments worth roughly ``overlap`` characters."""
        carried: list[TranscriptSegment] = []
        length = 0
        for seg in reversed(window):
            seg_len = len(clean_text(seg.text)) + 1
            if length >= self.overlap:
                break
            carried.insert(0, seg)
            length += seg_len
        return carried, length

    @staticmethod
    def _window_text(window: list[TranscriptSegment]) -> str:
        return clean_text(" ".join(s.text for s in window))

    def _build_chunk(
        self,
        window: list[TranscriptSegment],
        analysis_id: str,
        video_id: VideoSlot,
        platform: Platform,
        chunk_index: int,
    ) -> TranscriptChunk:
        start = window[0].start
        end = window[-1].start + window[-1].duration
        text = self._window_text(window)
        meta = ChunkMetadata(
            analysis_id=analysis_id,
            video_id=video_id,
            chunk_index=chunk_index,
            timestamp=timestamp_range(start, end),
            source_platform=platform,
        )
        return TranscriptChunk(
            id=f"{analysis_id}:{video_id}:{chunk_index}",
            text=text,
            metadata=meta,
        )


chunking_service = ChunkingService()
