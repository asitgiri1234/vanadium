"""Analysis snapshot + conversation memory store with disk persistence.

Snapshots, transcripts, visuals, and chat memory are kept in memory for fast
access and written to JSON files so ``analysis_id`` values survive backend
restarts. ChromaDB holds the vector index separately on disk.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    AnalysisSnapshot,
    ChatTurn,
    ComparisonInsights,
    TranscriptSegment,
    VideoSlot,
    VideoVisual,
)

logger = get_logger(__name__)


class AnalysisStore:
    def __init__(self, max_turns: int | None = None) -> None:
        self._lock = threading.Lock()
        self._snapshots: dict[str, AnalysisSnapshot] = {}
        self._memory: dict[str, list[ChatTurn]] = {}
        self._transcripts: dict[str, dict[VideoSlot, list[TranscriptSegment]]] = {}
        self._visuals: dict[str, dict[VideoSlot, VideoVisual]] = {}
        self._max_turns = max_turns or settings.memory_max_turns
        self._persist_dir = Path(settings.analysis_persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    # --- snapshots --- #
    def save(self, snapshot: AnalysisSnapshot) -> None:
        with self._lock:
            self._snapshots[snapshot.analysis_id] = snapshot
            self._persist(snapshot.analysis_id)

    def update_comparison(
        self, analysis_id: str, comparison: ComparisonInsights
    ) -> None:
        with self._lock:
            snap = self._snapshots.get(analysis_id)
            if snap is None:
                return
            self._snapshots[analysis_id] = snap.model_copy(
                update={"comparison": comparison}
            )
            self._persist(analysis_id)

    def get(self, analysis_id: str) -> AnalysisSnapshot | None:
        with self._lock:
            snap = self._snapshots.get(analysis_id)
            if snap is not None:
                return snap
            if self._load_file(self._path(analysis_id)):
                return self._snapshots.get(analysis_id)
            return None

    def exists(self, analysis_id: str) -> bool:
        with self._lock:
            if analysis_id in self._snapshots:
                return True
            return self._path(analysis_id).is_file()

    # --- transcripts --- #
    def save_transcripts(
        self, analysis_id: str, transcripts: dict[VideoSlot, list[TranscriptSegment]]
    ) -> None:
        with self._lock:
            self._transcripts[analysis_id] = transcripts

    def get_transcripts(
        self, analysis_id: str,
    ) -> dict[VideoSlot, list[TranscriptSegment]] | None:
        with self._lock:
            stored = self._transcripts.get(analysis_id)
            if stored is None and self._path(analysis_id).is_file():
                self._load_file(self._path(analysis_id))
                stored = self._transcripts.get(analysis_id)
            return {k: list(v) for k, v in stored.items()} if stored else None

    # --- visuals --- #
    def save_visuals(
        self, analysis_id: str, visuals: dict[VideoSlot, VideoVisual]
    ) -> None:
        with self._lock:
            self._visuals[analysis_id] = visuals

    def get_visuals(self, analysis_id: str) -> dict[VideoSlot, VideoVisual] | None:
        with self._lock:
            stored = self._visuals.get(analysis_id)
            if stored is None and self._path(analysis_id).is_file():
                self._load_file(self._path(analysis_id))
                stored = self._visuals.get(analysis_id)
            return dict(stored) if stored else None

    # --- conversation memory --- #
    def get_memory(self, analysis_id: str) -> list[ChatTurn]:
        with self._lock:
            if analysis_id not in self._memory and self._path(analysis_id).is_file():
                self._load_file(self._path(analysis_id))
            return list(self._memory.get(analysis_id, []))

    def append_turn(self, analysis_id: str, role: str, content: str) -> None:
        with self._lock:
            if analysis_id not in self._snapshots and self._path(analysis_id).is_file():
                self._load_file(self._path(analysis_id))
            turns = self._memory.setdefault(analysis_id, [])
            turns.append(ChatTurn(role=role, content=content))  # type: ignore[arg-type]
            limit = self._max_turns * 2
            if len(turns) > limit:
                del turns[: len(turns) - limit]
            self._persist(analysis_id)

    def clear_memory(self, analysis_id: str) -> None:
        with self._lock:
            self._memory.pop(analysis_id, None)
            if analysis_id in self._snapshots:
                self._persist(analysis_id)

    # --- persistence --- #
    def _path(self, analysis_id: str) -> Path:
        return self._persist_dir / f"{analysis_id}.json"

    def _persist(self, analysis_id: str) -> None:
        snap = self._snapshots.get(analysis_id)
        if snap is None:
            return

        transcripts = self._transcripts.get(analysis_id, {})
        visuals = self._visuals.get(analysis_id, {})
        memory = self._memory.get(analysis_id, [])

        payload: dict[str, Any] = {
            "snapshot": snap.model_dump(mode="json"),
            "transcripts": {
                slot: [seg.model_dump(mode="json") for seg in segs]
                for slot, segs in transcripts.items()
            },
            "visuals": {
                slot: vis.model_dump(mode="json") for slot, vis in visuals.items()
            },
            "memory": [turn.model_dump(mode="json") for turn in memory],
        }

        path = self._path(analysis_id)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError as exc:
            logger.warning("Failed to persist analysis %s: %s", analysis_id, exc)
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _load_all(self) -> None:
        loaded = 0
        for path in sorted(self._persist_dir.glob("*.json")):
            if self._load_file(path):
                loaded += 1
        if loaded:
            logger.info("Restored %d analysis(es) from %s", loaded, self._persist_dir)

    def _load_file(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            snap = AnalysisSnapshot.model_validate(data["snapshot"])
            aid = snap.analysis_id

            transcripts: dict[VideoSlot, list[TranscriptSegment]] = {}
            for slot, segs in (data.get("transcripts") or {}).items():
                transcripts[slot] = [  # type: ignore[index]
                    TranscriptSegment.model_validate(s) for s in segs
                ]

            visuals: dict[VideoSlot, VideoVisual] = {}
            for slot, vis in (data.get("visuals") or {}).items():
                visuals[slot] = VideoVisual.model_validate(vis)  # type: ignore[index]

            memory = [
                ChatTurn.model_validate(t) for t in (data.get("memory") or [])
            ]

            self._snapshots[aid] = snap
            if transcripts:
                self._transcripts[aid] = transcripts
            if visuals:
                self._visuals[aid] = visuals
            if memory:
                self._memory[aid] = memory
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping corrupt analysis file %s: %s", path.name, exc)
            return False


analysis_store = AnalysisStore()
