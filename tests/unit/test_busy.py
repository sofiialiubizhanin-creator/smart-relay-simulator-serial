"""Component tests for the toggle rate limit and the clocks (plan 13.4: D13, D14). Not AC coverage.

Simulated time only: ManualClock is moved with advance_time, and MonotonicClock gets a fake
time source. Nothing here waits in real time.
"""
import math

import pytest

from relay_sim.clock import ManualClock, MonotonicClock
from relay_sim.protocol import TOO_LONG
from relay_sim.relay import OFF, ON, TOGGLE_WINDOW_SECONDS, RelayDevice

OK, BUSY = b"OK\n", b"ERR BUSY\n"


@pytest.fixture
def dev():
    return RelayDevice()  # ManualClock at 0.0, no previous toggle


def test_window_is_two_seconds():
    assert TOGGLE_WINDOW_SECONDS == 2.0


def test_first_toggle_is_never_busy(dev):
    assert dev.handle_line(b"ON") == OK


@pytest.mark.parametrize("elapsed, response, state", [(0.0, BUSY, ON), (1.9, BUSY, ON), (2.0, OK, OFF), (2.5, OK, OFF)])
def test_window_boundary(dev, elapsed, response, state):
    dev.handle_line(b"ON")
    dev.advance_time(elapsed)
    assert dev.handle_line(b"OFF") == response
    assert dev.get_state() == state


def test_rejected_toggle_does_not_restart_window(dev):
    dev.handle_line(b"ON")
    dev.advance_time(1.5)
    assert dev.handle_line(b"OFF") == BUSY
    dev.advance_time(0.5)  # 2.0 s after the accepted toggle, 0.5 s after the rejection
    assert dev.handle_line(b"OFF") == OK


def test_accepted_toggle_restarts_window(dev):
    dev.handle_line(b"ON")
    dev.advance_time(2.0)
    assert dev.handle_line(b"OFF") == OK
    dev.advance_time(1.9)
    assert dev.handle_line(b"ON") == BUSY


def test_non_toggles_are_never_busy_and_keep_the_window(dev):
    dev.handle_line(b"ON")
    assert dev.handle_line(b"ON") == OK
    assert dev.handle_line(b"STATUS") == b"STATUS ON\n"
    dev.advance_time(1.5)
    assert dev.handle_line(b"ON") == OK
    dev.advance_time(0.5)
    assert dev.handle_line(b"OFF") == OK


def test_reset_clears_window(dev):
    dev.handle_line(b"ON")
    dev.reset()
    assert dev.handle_line(b"ON") == OK


def test_set_state_is_not_a_toggle(dev):
    dev.set_state(ON)
    assert dev.handle_line(b"OFF") == OK  # no window was started


def test_set_state_does_not_restart_window(dev):
    dev.handle_line(b"ON")
    dev.advance_time(1.0)
    dev.set_state(ON)
    dev.advance_time(1.0)  # 2.0 s after the accepted toggle
    assert dev.handle_line(b"OFF") == OK


@pytest.mark.parametrize(
    "setup, line, response",
    [
        (lambda d: None, b"off", b"ERR UNKNOWN_CMD\n"),
        (lambda d: None, b"", b"ERR EMPTY\n"),
        (lambda d: None, TOO_LONG, b"ERR TOO_LONG\n"),
        (lambda d: d.set_fault(True), b"OFF", b"ERR FAULT\n"),
        (lambda d: d.set_silent(True), b"OFF", None),
    ],
    ids=["unknown", "empty", "too_long", "fault", "silent"],
)
def test_other_outcomes_take_precedence_over_busy(dev, setup, line, response):
    dev.handle_line(b"ON")
    setup(dev)
    assert dev.handle_line(line) == response
    assert dev.get_state() == ON


# --- MonotonicClock (D14) ----------------------------------------------------

class FakeTime:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_monotonic_clock_follows_its_source():
    src = FakeTime()
    clock = MonotonicClock(src)
    assert clock.now() == 0.0
    src.t += 1.25
    assert clock.now() == 1.25


def test_monotonic_clock_advance_and_reset():
    src = FakeTime()
    clock = MonotonicClock(src)
    src.t += 1.0
    clock.advance(0.5)
    assert clock.now() == 1.5
    clock.reset()
    assert clock.now() == 0.0
    src.t += 0.25
    assert clock.now() == 0.25


@pytest.mark.parametrize("bad", [-1, math.nan])
def test_monotonic_clock_rejects_negative_or_nan(bad):
    with pytest.raises(ValueError):
        MonotonicClock(FakeTime()).advance(bad)


def test_busy_on_real_time_clock():
    src = FakeTime()
    dev = RelayDevice(MonotonicClock(src))
    assert dev.handle_line(b"ON") == OK
    src.t += 1.9
    assert dev.handle_line(b"OFF") == BUSY
    src.t += 0.1
    assert dev.handle_line(b"OFF") == OK


def test_relay_sim_uses_real_time_clock(monkeypatch):
    import relay_sim.__main__ as main_module

    seen = {}

    class FakeSimulator:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def start(self):
            raise OSError("stop here")  # main() reports a start failure and returns 1; no port is opened

    monkeypatch.setattr(main_module, "Simulator", FakeSimulator)
    assert main_module.main(["-q"]) == 1
    assert isinstance(seen["clock"], MonotonicClock)
