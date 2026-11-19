"""Component tests for `relay-host shell` (plan 12.4). Not AC coverage.

The shell runs as a real subprocess with piped stdin (so no prompt). stdout is
captured as bytes so newline translation can't hide a "\\r\\n".
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from relay_sim.exchange_log import RX
from relay_sim.simulator import Simulator
from tests.e2e.helpers import wait_until

SRC = str(Path(__file__).resolve().parents[2] / "src")


@pytest.fixture(scope="module")
def sim():
    with Simulator(port=0, control_port=0) as s:
        yield s


@pytest.fixture(autouse=True)
def clean(sim):
    sim.device.reset()
    sim.log.clear()


def env_for(address: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "RELAY_HOST_ADDRESS"}
    env.update(PYTHONPATH=SRC, RELAY_HOST_ADDRESS=address)
    return env


def shell(address: str, stdin: bytes, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "relay_host", *args, "shell"],
        input=stdin, env=env_for(address), capture_output=True, timeout=60,
    )


def addr(sim) -> str:
    return f"127.0.0.1:{sim.serial_port}"


def rx(sim) -> list[bytes]:
    return [e.data for e in sim.log.entries() if e.direction == RX]


def test_lines_are_sent_as_typed_and_responses_printed_in_order(sim):
    # Changed by C2: the last line was OFF, a second toggle with no time passing (piped input
    # can't advance the clock between lines), so it now gets ERR BUSY. STATUS keeps the test's
    # intent: every line is sent as typed and every response is printed in order.
    r = shell(addr(sim), b"ON\nSTATUS\non\n\nSTATUS\n")
    assert r.returncode == 0
    assert r.stdout == b"OK\nSTATUS ON\nERR UNKNOWN_CMD\nERR EMPTY\nSTATUS ON\n"
    assert r.stderr == b""
    assert rx(sim) == [b"ON", b"STATUS", b"on", b"", b"STATUS"]


def test_crlf_line_endings_are_removed(sim):
    r = shell(addr(sim), b"ON\r\nSTATUS\r\n")
    assert r.stdout == b"OK\nSTATUS ON\n"
    assert rx(sim) == [b"ON", b"STATUS"]


def test_last_line_without_newline_is_sent(sim):
    r = shell(addr(sim), b"STATUS")
    assert (r.returncode, r.stdout) == (0, b"STATUS OFF\n")


def test_line_is_sent_unchanged_including_spaces_tabs_and_utf8(sim):
    r = shell(addr(sim), " ON\n\tSTATUS\nÖN\n".encode("utf-8"))
    assert r.stdout == b"ERR UNKNOWN_CMD\n" * 3
    assert rx(sim) == [b" ON", b"\tSTATUS", "ÖN".encode("utf-8")]


def test_no_prompt_when_input_is_piped(sim):
    r = shell(addr(sim), b"STATUS\n")
    assert b"relay>" not in r.stdout


def test_empty_input_sends_nothing_and_exits_0(sim):
    r = shell(addr(sim), b"")
    assert (r.returncode, r.stdout) == (0, b"")
    assert rx(sim) == []


def test_extra_argument_is_usage_error(sim):
    r = subprocess.run(
        [sys.executable, "-m", "relay_host", "shell", "ON"],
        input=b"STATUS\n", env=env_for(addr(sim)), capture_output=True, timeout=30,
    )
    assert r.returncode == 2
    assert r.stdout == b""
    assert r.stderr != b""
    assert rx(sim) == []


def test_silent_device_one_stderr_line_per_input_line_and_continues(sim):
    sim.device.set_silent(True)
    r = shell(addr(sim), b"STATUS\nON\n", "--timeout", "0.3")
    assert r.returncode == 0
    assert r.stdout == b""
    assert len([line for line in r.stderr.splitlines() if line.strip()]) == 2
    assert sim.device.get_state() == "OFF"


@pytest.mark.parametrize("address", ["127.0.0.1", ""])
def test_invalid_address_one_stderr_line_per_input_line(address):
    r = shell(address, b"STATUS\nSTATUS\nSTATUS\n")
    assert r.returncode == 0
    assert r.stdout == b""
    assert len([line for line in r.stderr.splitlines() if line.strip()]) == 3


BOM = b"\xef\xbb\xbf"


def test_leading_bom_is_dropped(sim):
    r = shell(addr(sim), BOM + b"ON\r\nSTATUS\r\n")
    assert (r.returncode, r.stdout) == (0, b"OK\nSTATUS ON\n")
    assert rx(sim) == [b"ON", b"STATUS"]


def test_only_the_first_bom_at_the_very_start_is_dropped(sim):
    r = shell(addr(sim), BOM + BOM + b"ON\n" + BOM + b"OFF\n")
    assert r.stdout == b"ERR UNKNOWN_CMD\nERR UNKNOWN_CMD\n"
    assert rx(sim) == [BOM + b"ON", BOM + b"OFF"]


def test_bom_only_input_sends_nothing(sim):
    r = shell(addr(sim), BOM)
    assert (r.returncode, r.stdout) == (0, b"")
    assert rx(sim) == []


def test_bom_then_empty_line_sends_empty_line(sim):
    r = shell(addr(sim), BOM + b"\n")
    assert r.stdout == b"ERR EMPTY\n"


def test_errors_and_responses_can_mix(sim):
    sim.device.set_fault(True)
    r = shell(addr(sim), b"ON\nSTATUS\n")
    assert (r.returncode, r.stdout) == (0, b"ERR FAULT\nERR FAULT\n")


def test_idle_shell_holds_no_connection(sim):
    proc = subprocess.Popen(
        [sys.executable, "-m", "relay_host", "shell"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_for(addr(sim)),
    )
    try:
        proc.stdin.write(b"STATUS\n")
        proc.stdin.flush()
        wait_until(lambda: rx(sim) == [b"STATUS"], timeout=10, message="shell never sent its line")
        # The shell is now idle, waiting for input. Another client must be served at once.
        with socket.create_connection(("127.0.0.1", sim.serial_port), timeout=2) as sock:
            sock.sendall(b"ON\n")
            with sock.makefile("rb") as replies:
                assert replies.readline() == b"OK\n"
        out, err = proc.communicate(b"STATUS\n", timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.returncode == 0
    assert out == b"STATUS OFF\nSTATUS ON\n"


def test_single_commands_unchanged(sim):
    r = subprocess.run(
        [sys.executable, "-m", "relay_host", "send", "ÖN"], env=env_for(addr(sim)), capture_output=True, timeout=30
    )
    assert (r.returncode, r.stdout) == (1, b"ERR UNKNOWN_CMD\n")
    assert rx(sim) == ["ÖN".encode("utf-8")]
