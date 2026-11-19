"""Control API server, used only by tests (req §5; plan 5.1, 5.2, §0.1).

It calls RelayDevice methods directly and never goes through the serial protocol.
Control traffic is not written to the exchange log.
"""
from __future__ import annotations

import math
import os
import socket
import socketserver
import threading

from .exchange_log import ExchangeLog
from .protocol import LineReader, _TooLong
from .relay import STATES, RelayDevice

_POLL_SECONDS = 0.2
_MAX_LINE = 256
_SWITCH = {"ON": True, "OFF": False}


class ControlError(Exception):
    """A control command was rejected. The message becomes 'ERR <message>'."""


def execute(device: RelayDevice, log: ExchangeLog, line: bytes) -> bytes:
    """Run one control command and return its response line (without '\\n')."""
    try:
        return _execute(device, log, line).encode("ascii")
    except ControlError as exc:
        return f"ERR {exc}".encode("ascii")


def _execute(device: RelayDevice, log: ExchangeLog, line: bytes) -> str:
    try:
        text = line.decode("ascii")
    except UnicodeDecodeError:
        raise ControlError("non-ASCII command") from None
    parts = text.split(" ")
    name, args = parts[0], parts[1:]

    if name == "GET_STATE":
        _expect_args(args, 0)
        return device.get_state()
    if name == "RESET":
        _expect_args(args, 0)
        device.reset()
        log.clear()
        return "OK"
    if name == "SET_STATE":
        _expect_args(args, 1)
        if args[0] not in STATES:
            raise ControlError(f"bad state {args[0]!r}, expected ON or OFF")
        device.set_state(args[0])
        return "OK"
    if name in ("FAULT", "SILENCE"):
        _expect_args(args, 1)
        if args[0] not in _SWITCH:
            raise ControlError(f"bad value {args[0]!r}, expected ON or OFF")
        (device.set_fault if name == "FAULT" else device.set_silent)(_SWITCH[args[0]])
        return "OK"
    if name == "ADVANCE_TIME":
        _expect_args(args, 1)
        try:
            seconds = float(args[0])
        except ValueError:
            raise ControlError(f"bad seconds {args[0]!r}") from None
        if not math.isfinite(seconds) or seconds < 0:
            raise ControlError(f"bad seconds {args[0]!r}, expected a non-negative number")
        device.advance_time(seconds)
        return "OK"
    raise ControlError(f"unknown command {name!r}")


def _expect_args(args: list[str], n: int) -> None:
    if len(args) != n:
        raise ControlError(f"expected {n} argument(s), got {len(args)}")


class _ControlHandler(socketserver.BaseRequestHandler):
    server: "ControlServer"

    def handle(self) -> None:
        sock: socket.socket = self.request
        sock.settimeout(_POLL_SECONDS)
        reader = LineReader(max_bytes=_MAX_LINE)
        while not self.server.stopping.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return
            for line in reader.feed(data):
                if isinstance(line, _TooLong):
                    response = b"ERR line too long"
                else:
                    response = execute(self.server.device, self.server.log, line)
                try:
                    sock.sendall(response + b"\n")
                except OSError:
                    return


class ControlServer(socketserver.ThreadingTCPServer):
    """Accepts several control connections at once (one thread each)."""

    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def __init__(self, address: tuple[str, int], device: RelayDevice, log: ExchangeLog) -> None:
        self.device = device
        self.log = log
        self.stopping = threading.Event()
        super().__init__(address, _ControlHandler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def shutdown(self) -> None:
        self.stopping.set()
        super().shutdown()
