from __future__ import annotations

from collections import deque
from datetime import datetime


class EventLog:
    """A small, bounded feed of noteworthy events (arrivals, completions,
    errors) for the live dashboard - deliberately separate from the
    (much noisier, file-only) logging stream, so the console feed stays
    readable instead of drowning in every cooldown check."""

    def __init__(self, maxlen: int = 10):
        self._events: deque[str] = deque(maxlen=maxlen)

    def record(self, character_name: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._events.appendleft(f"[{timestamp}] {character_name}: {message}")

    def recent(self) -> list[str]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()


EVENT_LOG = EventLog()
