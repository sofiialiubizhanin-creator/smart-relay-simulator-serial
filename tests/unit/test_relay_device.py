"""Component tests for RelayDevice and ManualClock (plan 3.1, 3.2, 3.4, 3.5). Not AC coverage."""
import math

import pytest

from relay_sim.clock import ManualClock
from relay_sim.protocol import TOO_LONG
from relay_sim.relay import OFF, ON, RelayDevice


@pytest.fixture
def dev():
    return RelayDevice()


# --- commands (req §2.2, §2.3) ---------------------------------------------

def test_initial_state_is_off(dev):
    assert dev.get_state() == OFF
    assert dev.handle_line(b"STATUS") == b"STATUS OFF\n"


def test_on_off_status(dev):
    assert dev.handle_line(b"ON") == b"OK\n"
    assert dev.get_state() == ON
    assert dev.handle_line(b"STATUS") == b"STATUS ON\n"
    dev.advance_time(2)  # Changed by C2: a second toggle needs 2 s, or it gets ERR BUSY
    assert dev.handle_line(b"OFF") == b"OK\n"
    assert dev.get_state() == OFF


def test_repeated_on_and_off_are_ok_and_change_nothing(dev):
    dev.set_state(ON)
    assert dev.handle_line(b"ON") == b"OK\n"
    assert dev.get_state() == ON
    dev.set_state(OFF)
    assert dev.handle_line(b"OFF") == b"OK\n"
    assert dev.get_state() == OFF


# --- errors (req §3) ---------------------------------------------------------

UNKNOWN = [
    b"on", b"On", b"oN", b"off", b"Off", b"status", b"Status",
    b" ON", b"ON ", b"ON 1", b"\tSTATUS", b"TOGGLE",
    "ÖN".encode("utf-8"), b"\xffON", b"O\rN", b"\r", b"X" * 32,
]


@pytest.mark.parametrize("line", UNKNOWN, ids=repr)
@pytest.mark.parametrize("start", [OFF, ON])
def test_unknown_lines(dev, start, line):
    dev.set_state(start)
    assert dev.handle_line(line) == b"ERR UNKNOWN_CMD\n"
    assert dev.get_state() == start


@pytest.mark.parametrize("start", [OFF, ON])
def test_empty_line(dev, start):
    dev.set_state(start)
    assert dev.handle_line(b"") == b"ERR EMPTY\n"
    assert dev.get_state() == start


@pytest.mark.parametrize("start", [OFF, ON])
def test_too_long(dev, start):
    dev.set_state(start)
    assert dev.handle_line(TOO_LONG) == b"ERR TOO_LONG\n"
    assert dev.get_state() == start


# --- precedence (req §2.5) ---------------------------------------------------

ANY_LINE = [b"ON", b"OFF", b"STATUS", b"", TOO_LONG, b"TOGGLE", b"on"]


@pytest.mark.parametrize("line", ANY_LINE, ids=repr)
def test_silent_beats_everything_including_fault(dev, line):
    dev.set_silent(True)
    dev.set_fault(True)
    assert dev.handle_line(line) is None
    assert dev.get_state() == OFF


@pytest.mark.parametrize("line", ANY_LINE, ids=repr)
def test_silent_does_not_execute_commands(dev, line):
    dev.set_silent(True)
    assert dev.handle_line(line) is None
    assert dev.get_state() == OFF


@pytest.mark.parametrize("line", ANY_LINE, ids=repr)
@pytest.mark.parametrize("start", [OFF, ON])
def test_fault_beats_too_long_empty_unknown_and_valid(dev, start, line):
    dev.set_state(start)
    dev.set_fault(True)
    assert dev.handle_line(line) == b"ERR FAULT\n"
    assert dev.get_state() == start


def test_every_response_is_one_ascii_line(dev):
    # Since C2 the OFF below gets ERR BUSY (no time passes after ON). That is still one ASCII
    # line, so the check holds; the sequence now also covers the ERR BUSY response.
    responses = [dev.handle_line(x) for x in [b"ON", b"STATUS", b"OFF", b"STATUS", b"", TOO_LONG, b"x"]]
    dev.set_fault(True)
    responses.append(dev.handle_line(b"ON"))
    for r in responses:
        assert r.endswith(b"\n") and r.count(b"\n") == 1
        r.decode("ascii")


# --- control operations (req §5) --------------------------------------------

def test_clearing_fault_keeps_state(dev):
    dev.set_state(ON)
    dev.set_fault(True)
    dev.set_fault(False)
    assert dev.get_state() == ON
    assert dev.handle_line(b"STATUS") == b"STATUS ON\n"


def test_ending_silence_does_not_replay(dev):
    dev.set_silent(True)
    assert dev.handle_line(b"ON") is None
    dev.set_silent(False)
    assert dev.get_state() == OFF
    assert dev.handle_line(b"STATUS") == b"STATUS OFF\n"


def test_reset_restores_initial_condition(dev):
    dev.set_state(ON)
    dev.set_fault(True)
    dev.set_silent(True)
    dev.advance_time(5)
    dev.reset()
    assert (dev.get_state(), dev.fault, dev.silent, dev.clock.now()) == (OFF, False, False, 0.0)


def test_set_state_rejects_invalid_value(dev):
    with pytest.raises(ValueError):
        dev.set_state("on")


# --- clock (plan 3.1) ---------------------------------------------------------

def test_manual_clock_moves_only_when_advanced():
    clock = ManualClock()
    assert clock.now() == 0.0
    clock.advance(1.5)
    clock.advance(0.5)
    assert clock.now() == 2.0
    clock.reset()
    assert clock.now() == 0.0


@pytest.mark.parametrize("bad", [-1, math.nan])
def test_manual_clock_rejects_negative_or_nan(bad):
    with pytest.raises(ValueError):
        ManualClock().advance(bad)


def test_device_uses_injected_clock():
    clock = ManualClock()
    dev = RelayDevice(clock)
    dev.advance_time(3)
    assert clock.now() == 3.0
