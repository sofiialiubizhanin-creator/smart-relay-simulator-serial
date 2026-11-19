"""Component tests for the relay-host CLI and client (plan 6). Not AC coverage.

The CLI runs as a real subprocess. stdout is captured as bytes so newline
translation can't hide a "\\r\\n".
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from relay_host.client import DEFAULT_ADDRESS, HostConnectError, parse_address
from relay_sim.exchange_log import RX
from relay_sim.simulator import Simulator

SRC = str(Path(__file__).resolve().parents[2] / "src")


@pytest.fixture(scope="module")
def sim():
    with Simulator(port=0, control_port=0) as s:
        yield s


@pytest.fixture(autouse=True)
def clean(request):
    if "sim" in request.fixturenames:
        sim = request.getfixturevalue("sim")
        sim.device.reset()
        sim.log.clear()


def run(address: str | None, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "RELAY_HOST_ADDRESS"}
    env["PYTHONPATH"] = SRC
    if address is not None:
        env["RELAY_HOST_ADDRESS"] = address
    return subprocess.run(
        [sys.executable, "-m", "relay_host", *args], env=env, capture_output=True, timeout=30
    )


def addr(sim) -> str:
    return f"127.0.0.1:{sim.serial_port}"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def rx(sim) -> list[bytes]:
    return [e.data for e in sim.log.entries() if e.direction == RX]


# --- exit 0 / 1: device responded -------------------------------------------

def test_on_off_status(sim):
    r = run(addr(sim), "on")
    assert (r.returncode, r.stdout) == (0, b"OK\n")
    assert sim.device.get_state() == "ON"
    r = run(addr(sim), "status")
    assert (r.returncode, r.stdout) == (0, b"STATUS ON\n")
    r = run(addr(sim), "off")
    assert (r.returncode, r.stdout) == (0, b"OK\n")
    assert sim.device.get_state() == "OFF"


def test_device_error_exits_1(sim):
    r = run(addr(sim), "send", "on")
    assert (r.returncode, r.stdout) == (1, b"ERR UNKNOWN_CMD\n")
    assert sim.device.get_state() == "OFF"


@pytest.mark.parametrize(
    "line, wire, response",
    [
        ("\tSTATUS", b"\tSTATUS", b"ERR UNKNOWN_CMD\n"),
        (" ON", b" ON", b"ERR UNKNOWN_CMD\n"),
        ("", b"", b"ERR EMPTY\n"),
        ("\r", b"", b"ERR EMPTY\n"),  # trailing CR stripped by the device
        ("ON\r", b"ON", b"OK\n"),
        ("ÖN", "ÖN".encode("utf-8"), b"ERR UNKNOWN_CMD\n"),
        ("X" * 33, None, b"ERR TOO_LONG\n"),
    ],
    ids=repr,
)
def test_send_is_transparent(sim, line, wire, response):
    r = run(addr(sim), "send", line)
    assert r.stdout == response
    if wire is not None:
        assert rx(sim) == [wire]


def test_send_10000_bytes(sim):
    r = run(addr(sim), "send", "X" * 10_000)
    assert (r.returncode, r.stdout) == (1, b"ERR TOO_LONG\n")


def test_timeout_option_accepted(sim):
    r = run(addr(sim), "--timeout", "0.5", "status")
    assert (r.returncode, r.stdout) == (0, b"STATUS OFF\n")


# --- exit 2: usage errors, nothing sent -------------------------------------

@pytest.mark.parametrize(
    "args",
    [
        (),
        ("toggle",),
        ("send",),
        ("on", "extra"),
        ("send", "ON", "extra"),
        ("send", "ON\nOFF"),
        ("--timeout", "0", "on"),
        ("--timeout", "-1", "on"),
        ("--timeout", "abc", "on"),
        ("--timeout", "nan", "on"),
        ("--timeout", "inf", "on"),
        ("status", "--timeout", "0.3"),  # options go before the subcommand (D1)
    ],
    ids=repr,
)
def test_usage_errors_exit_2_and_send_nothing(sim, args):
    r = run(addr(sim), *args)
    assert r.returncode == 2
    assert r.stdout == b""
    assert r.stderr != b""
    assert rx(sim) == []
    assert sim.device.get_state() == "OFF"


# --- exit 3: no response ----------------------------------------------------

def test_silent_device_exits_3(sim):
    sim.device.set_silent(True)
    r = run(addr(sim), "--timeout", "0.3", "on")
    assert r.returncode == 3
    assert r.stdout == b""
    assert r.stderr != b""
    assert sim.device.get_state() == "OFF"


# --- exit 4: cannot connect / invalid address -------------------------------

def test_nothing_listening_exits_4():
    r = run(f"127.0.0.1:{free_port()}", "status")
    assert r.returncode == 4
    assert r.stdout == b""
    assert r.stderr != b""


@pytest.mark.parametrize("address", ["127.0.0.1", "127.0.0.1:abc", "127.0.0.1:0", "127.0.0.1:65536", ""])
def test_invalid_address_exits_4(address):
    r = run(address, "status")
    assert r.returncode == 4
    assert r.stdout == b""
    assert r.stderr != b""


# --- address parsing and isolation ------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [("127.0.0.1:5555", ("127.0.0.1", 5555)), ("localhost:1", ("localhost", 1)), ("h:65535", ("h", 65535))],
)
def test_parse_valid_address(value, expected):
    assert parse_address(value) == expected


@pytest.mark.parametrize(
    "value", ["", ":5555", "host", "host:", "host:0", "host:65536", "host:+1", "host:٥", "::1:5555", "a b:1"]
)
def test_parse_invalid_address(value):
    with pytest.raises(HostConnectError):
        parse_address(value)


def test_default_address():
    assert DEFAULT_ADDRESS == "127.0.0.1:5555"


def test_host_does_not_import_simulator():
    code = (
        "import sys, relay_host.cli, relay_host.client;"
        "bad = [m for m in sys.modules if m.startswith('relay_sim')];"
        "sys.exit(1 if bad else 0)"
    )
    env = dict(os.environ, PYTHONPATH=SRC)
    assert subprocess.run([sys.executable, "-c", code], env=env).returncode == 0
