"""Helpers for the E2E suite.

Contract: .claude/skills/e2e-test-conventions/references/fixtures-and-control-api.md
"""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Callable

# The one allowed shorter host timeout, only for silent-device tests (F1-AC-15, F1-AC-16).
SHORT_TIMEOUT = "0.3"

# Exit code requirements.md §4.3 assigns to "no response within the timeout".
_EXIT_NO_RESPONSE = 3


@dataclass(frozen=True)
class HostResult:
    """What one relay-host run produced."""

    exit_code: int
    stdout: str
    stderr: str
    elapsed: float

    @property
    def response(self) -> str | None:
        """stdout without its trailing line terminator, or None if stdout is empty."""
        if self.stdout == "":
            return None
        return self.stdout[:-1] if self.stdout.endswith("\n") else self.stdout

    @property
    def timed_out(self) -> bool:
        return self.exit_code == _EXIT_NO_RESPONSE


def expect_response(result: HostResult, response: str, exit_code: int) -> None:
    """validation.md V2: stdout is exactly the response plus one "\\n", and the exit code is exact."""
    assert result.stdout == response + "\n", f"stdout {result.stdout!r}, expected {response + chr(10)!r}"
    assert result.exit_code == exit_code, (
        f"exit code {result.exit_code}, expected {exit_code} (stderr {result.stderr!r})"
    )


def expect_no_response(result: HostResult, exit_code: int) -> None:
    """validation.md V3: for exit codes 2, 3 and 4, stdout is empty and stderr is not."""
    assert result.exit_code == exit_code, (
        f"exit code {result.exit_code}, expected {exit_code} (stdout {result.stdout!r}, stderr {result.stderr!r})"
    )
    assert result.stdout == "", f"stdout should be empty, was {result.stdout!r}"
    assert result.stderr != "", "stderr should contain a short message"


def wait_until(
    condition: Callable[[], object],
    timeout: float,
    interval: float = 0.05,
    message: str | None = None,
) -> None:
    """Poll `condition` until it is truthy, or fail the test after `timeout` real seconds."""
    deadline = time.monotonic() + timeout
    while True:
        if condition():
            return
        if time.monotonic() >= deadline:
            raise AssertionError(message or f"condition not met within {timeout} s")
        time.sleep(interval)  # the only sleep allowed in the E2E suite


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
