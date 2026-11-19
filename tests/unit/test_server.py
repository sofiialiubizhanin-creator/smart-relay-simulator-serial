"""Component tests for the serial server, exchange log and Simulator (plan 4). Not AC coverage.

Uses socket read timeouts to detect "no response"; there is no sleep.
"""
import socket

import pytest

from relay_sim.exchange_log import RX, TOO_LONG_PLACEHOLDER, TX
from relay_sim.relay import ON
from relay_sim.simulator import Simulator

NO_RESPONSE_WAIT = 0.3


@pytest.fixture
def sim():
    with Simulator(port=0, control_port=0) as s:
        yield s


def connect(sim) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", sim.serial_port), timeout=2)
    return sock


def read_line(sock: socket.socket) -> bytes:
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("closed before a full line")
        buf += chunk
    return buf


def assert_no_response(sock: socket.socket) -> None:
    sock.settimeout(NO_RESPONSE_WAIT)
    with pytest.raises(socket.timeout):
        sock.recv(1)
    sock.settimeout(2)


@pytest.mark.parametrize(
    "send, expected",
    [
        (b"STATUS\n", b"STATUS OFF\n"),
        (b"ON\n", b"OK\n"),
        (b"OFF\n", b"OK\n"),
        (b"ON\r\n", b"OK\n"),
        (b"on\n", b"ERR UNKNOWN_CMD\n"),
        (b"\n", b"ERR EMPTY\n"),
        (b"\r\n", b"ERR EMPTY\n"),
        (b"X" * 33 + b"\n", b"ERR TOO_LONG\n"),
        (b"X" * 32 + b"\r\n", b"ERR UNKNOWN_CMD\n"),
    ],
    ids=repr,
)
def test_responses(sim, send, expected):
    with connect(sim) as sock:
        sock.sendall(send)
        assert read_line(sock) == expected


def test_several_commands_on_one_connection(sim):
    with connect(sim) as sock:
        sock.sendall(b"ON\nSTATUS\n")
        assert [read_line(sock) for _ in range(2)] == [b"OK\n", b"STATUS ON\n"]
        sim.device.advance_time(2)  # Changed by C2: a second toggle needs 2 s, or it gets ERR BUSY
        sock.sendall(b"OFF\nSTATUS\n")
        assert [read_line(sock) for _ in range(2)] == [b"OK\n", b"STATUS OFF\n"]
    assert sim.device.get_state() == "OFF"


def test_line_split_across_writes(sim):
    with connect(sim) as sock:
        for b in b"STATUS\r\n":
            sock.sendall(bytes([b]))
        assert read_line(sock) == b"STATUS OFF\n"


def test_very_long_line_gives_one_error_and_connection_keeps_working(sim):
    with connect(sim) as sock:
        sock.sendall(b"X" * 10_000 + b"\n")
        assert read_line(sock) == b"ERR TOO_LONG\n"
        sock.sendall(b"STATUS\n")
        assert read_line(sock) == b"STATUS OFF\n"
    tx = [e.data for e in sim.log.entries() if e.direction == TX]
    assert tx == [b"ERR TOO_LONG", b"STATUS OFF"]


def test_fault_and_silence(sim):
    with connect(sim) as sock:
        sim.device.set_fault(True)
        sock.sendall(b"ON\n")
        assert read_line(sock) == b"ERR FAULT\n"
        sim.device.set_silent(True)
        sock.sendall(b"ON\n")
        assert_no_response(sock)
    assert sim.device.get_state() == "OFF"


def test_partial_line_is_dropped_on_close(sim):
    with connect(sim) as sock:
        sock.sendall(b"ON")
    with connect(sim) as sock:
        sock.sendall(b"\n")
        assert read_line(sock) == b"ERR EMPTY\n"
    assert sim.device.get_state() == "OFF"


def test_one_connection_at_a_time(sim):
    first = connect(sim)
    second = connect(sim)  # accepted by the OS, waits in the backlog
    try:
        second.sendall(b"STATUS\n")
        assert_no_response(second)
        first.close()
        assert read_line(second) == b"STATUS OFF\n"
    finally:
        first.close()
        second.close()


def test_exchange_log_records_rx_and_tx_with_timestamps(sim):
    sim.device.set_state(ON)
    with connect(sim) as sock:
        sock.sendall(b"STATUS\n" + b"Y" * 40 + b"\n")
        read_line(sock)
        read_line(sock)
    entries = sim.log.entries()
    assert [(d, data) for _, d, data in entries] == [
        (RX, b"STATUS"),
        (TX, b"STATUS ON"),
        (RX, TOO_LONG_PLACEHOLDER),
        (TX, b"ERR TOO_LONG"),
    ]
    timestamps = [t for t, _, _ in entries]
    assert timestamps == sorted(timestamps)
    assert all(t.tzinfo is not None for t in timestamps)


def test_silent_lines_are_still_logged_as_received(sim):
    sim.device.set_silent(True)
    with connect(sim) as sock:
        sock.sendall(b"ON\n")
        assert_no_response(sock)
    assert [(d, data) for _, d, data in sim.log.entries()] == [(RX, b"ON")]


def test_stop_returns_while_a_client_is_still_connected():
    sim = Simulator(port=0, control_port=0).start()
    sock = connect(sim)
    try:
        sim.stop()  # must not hang on the open connection
    finally:
        sock.close()


def test_port_zero_picks_a_free_port(sim):
    assert sim.serial_port > 0
