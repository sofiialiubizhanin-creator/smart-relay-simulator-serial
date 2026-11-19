"""Injectable clocks (plan 3.1, D14).

- ManualClock moves only through advance() and reset(). The simulator uses it by default, so
  tests never depend on wall time.
- MonotonicClock follows real time. relay-sim uses it when run by hand (req §2.6).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Protocol


class Clock(Protocol):
    """What the simulator needs from a clock."""

    def now(self) -> float: ...
    def advance(self, seconds: float) -> None: ...
    def reset(self) -> None: ...


def _check_step(seconds: float) -> None:
    if not seconds >= 0:  # also rejects NaN
        raise ValueError(f"cannot advance the clock by {seconds!r}")


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
        _check_step(seconds)
        with self._lock:
            self._now += seconds

    def reset(self) -> None:
        with self._lock:
            self._now = self._start


class MonotonicClock:
    """A clock that follows real time; starts at 0.0.

    now() is the real time since creation or the last reset(), plus whatever advance() added,
    so the control API's ADVANCE_TIME still works. The time source is injectable, so tests
    of this clock never wait in real time.
    """

    def __init__(self, source: Callable[[], float] = time.monotonic) -> None:
        self._source = source
        self._lock = threading.Lock()
        self._base = source()
        self._offset = 0.0

    def now(self) -> float:
        with self._lock:
            return self._source() - self._base + self._offset

    def advance(self, seconds: float) -> None:
        _check_step(seconds)
        with self._lock:
            self._offset += seconds

    def reset(self) -> None:
        with self._lock:
            self._base = self._source()
            self._offset = 0.0
