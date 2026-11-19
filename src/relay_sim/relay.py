"""The relay state machine (req §2.2-§2.5, §3, §5; plan 3.2, 3.4, 3.5)."""
from __future__ import annotations

import threading

from .clock import Clock, ManualClock
from .protocol import Line, _TooLong

ON = "ON"
OFF = "OFF"
STATES = (ON, OFF)

OK = b"OK\n"
STATUS_ON = b"STATUS ON\n"
STATUS_OFF = b"STATUS OFF\n"
ERR_UNKNOWN_CMD = b"ERR UNKNOWN_CMD\n"
ERR_EMPTY = b"ERR EMPTY\n"
ERR_TOO_LONG = b"ERR TOO_LONG\n"
ERR_FAULT = b"ERR FAULT\n"


class RelayDevice:
    """One simulated relay. Thread-safe: all state is guarded by one lock."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock if clock is not None else ManualClock()
        self._lock = threading.RLock()
        self._state = OFF
        self._fault = False
        self._silent = False

    # --- serial protocol -------------------------------------------------

    def handle_line(self, line: Line) -> bytes | None:
        """Process one line. Returns the response, or None for no response.

        Precedence (req §2.5): silent, fault, too long, empty, unknown, valid.
        """
        with self._lock:
            if self._silent:
                return None
            if self._fault:
                return ERR_FAULT
            if isinstance(line, _TooLong):
                return ERR_TOO_LONG
            if line == b"":
                return ERR_EMPTY
            if line == b"ON":
                return self._command_set(ON)
            if line == b"OFF":
                return self._command_set(OFF)
            if line == b"STATUS":
                return STATUS_ON if self._state == ON else STATUS_OFF
            # Anything else, including lowercase, whitespace, arguments and
            # bytes above 0x7F, is unknown.
            return ERR_UNKNOWN_CMD

    def _command_set(self, target: str) -> bytes:
        if self._state == target:
            # Not a toggle: no state change (req §2.2, §9).
            return OK
        return self._toggle(target)

    def _toggle(self, target: str) -> bytes:
        # The only place a command changes the state. Phase 2's rate limit
        # check belongs here (plan §10).
        self._state = target
        return OK

    # --- control API -----------------------------------------------------

    def get_state(self) -> str:
        with self._lock:
            return self._state

    def set_state(self, state: str) -> None:
        if state not in STATES:
            raise ValueError(f"invalid state {state!r}")
        with self._lock:
            self._state = state

    def set_fault(self, enabled: bool) -> None:
        with self._lock:
            self._fault = enabled

    def set_silent(self, enabled: bool) -> None:
        with self._lock:
            self._silent = enabled

    @property
    def fault(self) -> bool:
        with self._lock:
            return self._fault

    @property
    def silent(self) -> bool:
        with self._lock:
            return self._silent

    @property
    def clock(self) -> Clock:
        return self._clock

    def advance_time(self, seconds: float) -> None:
        self._clock.advance(seconds)

    def reset(self) -> None:
        with self._lock:
            self._state = OFF
            self._fault = False
            self._silent = False
            self._clock.reset()
