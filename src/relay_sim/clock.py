"""Injectable clock. The simulator never reads wall time (plan 3.1)."""
from __future__ import annotations

import threading
from typing import Protocol


class Clock(Protocol):
    """What the simulator needs from a clock. Time moves only via advance() and reset()."""

    def now(self) -> float: ...
    def advance(self, seconds: float) -> None: ...
    def reset(self) -> None: ...


class ManualClock:
    """A clock that only moves when told to. Starts at 0.0."""

    def __init__(self, start: float = 0.0) -> None:
        self._start = start
        self._now = start
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._now

    def advance(self, seconds: float) -> None:
        if not seconds >= 0:  # also rejects NaN
            raise ValueError(f"cannot advance the clock by {seconds!r}")
        with self._lock:
            self._now += seconds

    def reset(self) -> None:
        with self._lock:
            self._now = self._start
