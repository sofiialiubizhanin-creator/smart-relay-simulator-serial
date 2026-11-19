"""Simulator facade: owns the device and log, runs the servers on threads (plan 4.3)."""
from __future__ import annotations

import socketserver
import threading

from .clock import Clock
from .control import ControlServer
from .exchange_log import ExchangeLog
from .relay import RelayDevice
from .server import SerialServer

DEFAULT_BIND = "127.0.0.1"
DEFAULT_SERIAL_PORT = 5555
DEFAULT_CONTROL_PORT = 5556


class Simulator:
    """Start with start() or a `with` block. Port 0 picks a free port."""

    def __init__(
        self,
        bind: str = DEFAULT_BIND,
        port: int = DEFAULT_SERIAL_PORT,
        control_port: int = DEFAULT_CONTROL_PORT,
        clock: Clock | None = None,
    ) -> None:
        self.device = RelayDevice(clock)
        self.log = ExchangeLog()
        self._bind = bind
        self._port = port
        self._control_port = control_port
        self._serial: SerialServer | None = None
        self._control: ControlServer | None = None
        self._threads: list[threading.Thread] = []

    @property
    def serial_port(self) -> int:
        if self._serial is None:
            raise RuntimeError("simulator is not started")
        return self._serial.port

    @property
    def control_port(self) -> int:
        if self._control is None:
            raise RuntimeError("simulator is not started")
        return self._control.port

    def start(self) -> "Simulator":
        try:
            self._serial = SerialServer((self._bind, self._port), self.device, self.log)
            self._control = ControlServer((self._bind, self._control_port), self.device, self.log)
        except OSError:
            self.stop()
            raise
        for name, server in (("relay-serial", self._serial), ("relay-control", self._control)):
            self._run(name, server)
        return self

    def _run(self, name: str, server: socketserver.BaseServer) -> None:
        t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, name=name, daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self) -> None:
        servers = [s for s in (self._serial, self._control) if s is not None]
        if any(t.is_alive() for t in self._threads):
            # Shut down in parallel: each shutdown() waits up to one poll interval.
            stoppers = [threading.Thread(target=s.shutdown) for s in servers]
            for t in stoppers:
                t.start()
            for t in stoppers:
                t.join(timeout=5)
        for server in servers:
            server.server_close()
        self._serial = self._control = None
        for t in self._threads:
            t.join(timeout=5)
        self._threads.clear()

    def __enter__(self) -> "Simulator":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
