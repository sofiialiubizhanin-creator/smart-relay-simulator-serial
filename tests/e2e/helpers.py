"""Helpers for the E2E suite (fixture contract: .claude/skills/e2e-test-conventions/references/).

Step 5 adds ControlClient. wait_until, HostResult and SHORT_TIMEOUT come in step 7.
"""
from __future__ import annotations

import socket


class ControlError(AssertionError):
    """The simulator's control API answered ERR. Fails the test, not errors it."""


class ControlClient:
    """Client for the simulator's control API (tests only; never used by the host)."""

    def __init__(self, port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._file = self._sock.makefile("rb")

    # --- contract methods ---------------------------------------------------

    def set_state(self, state: str) -> None:
        self.command(f"SET_STATE {state}")

    def get_state(self) -> str:
        return self.command("GET_STATE")

    def fault(self, enabled: bool = True) -> None:
        self.command(f"FAULT {'ON' if enabled else 'OFF'}")

    def silence(self, enabled: bool = True) -> None:
        self.command(f"SILENCE {'ON' if enabled else 'OFF'}")

    def reset(self) -> None:
        self.command("RESET")

    def advance_time(self, seconds: float) -> None:
        self.command(f"ADVANCE_TIME {seconds}")

    # --- plumbing -----------------------------------------------------------

    def command(self, line: str) -> str:
        """Send one control command and return its response. Raises ControlError on ERR."""
        self._sock.sendall(line.encode("ascii") + b"\n")
        raw = self._file.readline()
        if not raw.endswith(b"\n"):
            raise ConnectionError(f"control connection closed while waiting for a reply to {line!r}")
        response = raw[:-1].decode("ascii")
        if response.startswith("ERR"):
            raise ControlError(f"control command {line!r} failed: {response}")
        return response

    def close(self) -> None:
        self._file.close()
        self._sock.close()

    def __enter__(self) -> "ControlClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
