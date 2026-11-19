"""TCP server for the relay's serial port (plan 4.1, D7). Standard library only."""
from __future__ import annotations

import os
import socket
import socketserver
import threading

from .exchange_log import RX, TOO_LONG_PLACEHOLDER, TX, ExchangeLog
from .protocol import LineReader, _TooLong
from .relay import RelayDevice

_POLL_SECONDS = 0.2  # how often a handler checks for shutdown while idle


class _SerialHandler(socketserver.BaseRequestHandler):
    server: "SerialServer"

    def handle(self) -> None:
        sock: socket.socket = self.request
        sock.settimeout(_POLL_SECONDS)
        reader = LineReader()
        device, log = self.server.device, self.server.log
        while not self.server.stopping.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return  # client closed; any partial line is dropped (req §7)
            for line in reader.feed(data):
                log.add(RX, TOO_LONG_PLACEHOLDER if isinstance(line, _TooLong) else line)
                response = device.handle_line(line)
                if response is None:
                    continue
                try:
                    sock.sendall(response)
                except OSError:
                    return
                log.add(TX, response.rstrip(b"\n"))


class SerialServer(socketserver.TCPServer):
    """Serves one connection at a time. Other clients wait in the listen backlog."""

    allow_reuse_address = os.name != "nt"  # on Windows SO_REUSEADDR allows port sharing

    def __init__(self, address: tuple[str, int], device: RelayDevice, log: ExchangeLog) -> None:
        self.device = device
        self.log = log
        self.stopping = threading.Event()
        super().__init__(address, _SerialHandler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def shutdown(self) -> None:
        self.stopping.set()
        super().shutdown()
