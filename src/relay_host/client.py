"""Host client library: one command per connection over serial-over-TCP (req §4; plan 6.1).

Talks to the simulator only through the text protocol, via pyserial's socket:// URL.
It never imports relay_sim and never uses the control port (plan 6.5).
"""
from __future__ import annotations

import serial

DEFAULT_ADDRESS = "127.0.0.1:5555"
ADDRESS_ENV_VAR = "RELAY_HOST_ADDRESS"
DEFAULT_TIMEOUT = 1.0


class HostError(Exception):
    """Base class for host failures that have their own exit code."""


class HostConnectError(HostError):
    """Invalid address, or the connection could not be opened (exit 4)."""


class HostTimeout(HostError):
    """No full response line within the timeout (exit 3)."""


def parse_address(value: str) -> tuple[str, int]:
    """Validate HOST:PORT (req §4.1). IPv6 is not supported."""
    host, sep, port_text = value.rpartition(":")
    if not sep or not host or ":" in host or any(c.isspace() for c in host):
        raise HostConnectError(f"invalid address {value!r}, expected HOST:PORT")
    if not port_text.isascii() or not port_text.isdigit():
        raise HostConnectError(f"invalid port in address {value!r}")
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise HostConnectError(f"port out of range in address {value!r}")
    return host, port


class RelayClient:
    def __init__(self, address: str = DEFAULT_ADDRESS, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.address = address
        self.timeout = timeout

    def send_line(self, line: str) -> str:
        """Send one line and return the response without its trailing newline.

        The line is sent exactly as given, encoded as UTF-8, followed by "\\n" (req §4.2).
        """
        host, port = parse_address(self.address)
        try:
            port_obj = serial.serial_for_url(f"socket://{host}:{port}", timeout=self.timeout)
        except (serial.SerialException, OSError, ValueError) as exc:
            raise HostConnectError(f"cannot connect to {host}:{port}: {exc}") from exc
        try:
            try:
                port_obj.write(line.encode("utf-8") + b"\n")
                raw = port_obj.read_until(b"\n")  # the timeout covers the whole read
            except serial.SerialException as exc:
                # The device closed the connection before answering. F1 leaves this
                # case undefined (req §8); it is reported as "no response".
                raise HostTimeout(f"no response from {host}:{port}: {exc}") from exc
        finally:
            port_obj.close()
        if not raw.endswith(b"\n"):
            raise HostTimeout(f"no response from {host}:{port} within {self.timeout:g} s")
        return raw[:-1].decode("ascii", errors="replace")
