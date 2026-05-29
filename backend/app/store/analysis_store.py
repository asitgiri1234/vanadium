"""In-memory analysis snapshot + conversation memory store.

Deliberately tiny and behind a narrow interface so it can be swapped for Redis
(memory) and Postgres (snapshots) in production without touching callers.
"""

from __future__ import annotations

import threading

from app.core.config import settings
from app.models.schemas import AnalysisSnapshot, ChatTurn


class AnalysisStore:
    def __init__(self, max_turns: int | None = None) -> None:
        self._lock = threading.Lock()
        self._snapshots: dict[str, AnalysisSnapshot] = {}
        self._memory: dict[str, list[ChatTurn]] = {}
        self._max_turns = max_turns or settings.memory_max_turns

    # --- snapshots --- #
    def save(self, snapshot: AnalysisSnapshot) -> None:
        with self._lock:
            self._snapshots[snapshot.analysis_id] = snapshot

    def get(self, analysis_id: str) -> AnalysisSnapshot | None:
        with self._lock:
            return self._snapshots.get(analysis_id)

    def exists(self, analysis_id: str) -> bool:
        with self._lock:
            return analysis_id in self._snapshots

    # --- conversation memory --- #
    def get_memory(self, analysis_id: str) -> list[ChatTurn]:
        with self._lock:
            return list(self._memory.get(analysis_id, []))

    def append_turn(self, analysis_id: str, role: str, content: str) -> None:
        with self._lock:
            turns = self._memory.setdefault(analysis_id, [])
            turns.append(ChatTurn(role=role, content=content))  # type: ignore[arg-type]
            # Keep the last N turns (2 messages per exchange).
            limit = self._max_turns * 2
            if len(turns) > limit:
                del turns[: len(turns) - limit]

    def clear_memory(self, analysis_id: str) -> None:
        with self._lock:
            self._memory.pop(analysis_id, None)


analysis_store = AnalysisStore()
