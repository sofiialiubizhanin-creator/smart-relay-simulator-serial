"""In-memory log of every line the simulator receives and sends (plan 4.2, D8).

Timestamps are wall-clock and used only for reports. They never drive behaviour.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

RX = "RX"  # received by the simulator
TX = "TX"  # sent by the simulator

TOO_LONG_PLACEHOLDER = b"<line over 32 bytes, discarded>"


@dataclass(frozen=True)
class Entry:
    timestamp: datetime
    direction: str
    data: bytes

    def __iter__(self):  # allows: timestamp, direction, data = entry
        return iter((self.timestamp, self.direction, self.data))

    def format(self) -> str:
        return f"{self.timestamp.isoformat(timespec='milliseconds')} {self.direction} {self.data!r}"


class ExchangeLog:
    """Thread-safe, bounded log. Optional listeners see each entry as it is added."""

    def __init__(self, maxlen: int = 10_000) -> None:
        self._entries: deque[Entry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._listeners: list[Callable[[Entry], None]] = []

    def add(self, direction: str, data: bytes) -> Entry:
        entry = Entry(datetime.now().astimezone(), direction, data)
        with self._lock:
            self._entries.append(entry)
            listeners = list(self._listeners)
        for listener in listeners:
            listener(entry)
        return entry

    def entries(self) -> list[Entry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def subscribe(self, listener: Callable[[Entry], None]) -> None:
        with self._lock:
            self._listeners.append(listener)
