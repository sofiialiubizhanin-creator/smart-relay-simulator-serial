"""F1 E2E tests: toggle rate limit, change C2 (F1-AC-30 ... F1-AC-36).

Derived from specs/2026-11-18-relay-control/requirements.md §2.6 and §6, and validation.md
("Toggle rate limit (change C2)" and rule V7). Each test starts at t = 0 after the fixture's
reset, with no previous toggle. Simulated time moves only through control.advance_time; nothing
waits in real time. The window is opened with a real toggle through host, because SET_STATE is
not a toggle (req §2.6).
"""
from tests.e2e.helpers import expect_response


def test_F1_AC_30_toggle_within_2s_is_rejected(host, control):
    """F1-AC-30: A toggle less than 2 s after the previous one is rejected.

    From `OFF`, `relay-host on` prints `OK` (t = 0). At t = 1.9, `relay-host off` prints
    `ERR BUSY` and exits 1, and the state is still `ON`.
    """
    assert control.get_state() == "OFF"
    expect_response(host.on(), "OK", 0)

    control.advance_time(1.9)
    expect_response(host.off(), "ERR BUSY", 1)
    assert control.get_state() == "ON"


def test_F1_AC_31_toggle_exactly_2s_later_is_accepted(host, control):
    """F1-AC-31: A toggle exactly 2 s after the previous one is accepted.

    From `OFF`, `relay-host on` prints `OK` (t = 0). At t = 2.0, `relay-host off` prints `OK`
    and exits 0, and the state is `OFF`.
    """
    assert control.get_state() == "OFF"
    expect_response(host.on(), "OK", 0)

    control.advance_time(2.0)
    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF"


def test_F1_AC_32_rejected_toggle_does_not_restart_window(host, control):
    """F1-AC-32: A rejected toggle doesn't restart the window.

    From `OFF`, `relay-host on` prints `OK` (t = 0). At t = 1.5, `relay-host off` prints
    `ERR BUSY`. At t = 2.0, `relay-host off` prints `OK`, and the state is `OFF`.
    """
    assert control.get_state() == "OFF"
    expect_response(host.on(), "OK", 0)

    control.advance_time(1.5)
    expect_response(host.off(), "ERR BUSY", 1)
    assert control.get_state() == "ON"

    control.advance_time(0.5)  # t = 2.0: 2 s after the accepted toggle, 0.5 s after the rejected one
    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF", "the window must count from the last accepted toggle"


def test_F1_AC_33_non_toggles_never_busy_and_keep_window(host, control):
    """F1-AC-33: Non-toggles are never BUSY and don't restart the window.

    From `OFF`, `relay-host on` prints `OK` (t = 0). At t = 0, `relay-host on` prints `OK` and
    `relay-host status` prints `STATUS ON`, each exiting 0. At t = 1.5, `relay-host on` prints
    `OK`. At t = 2.0, `relay-host off` prints `OK`, and the state is `OFF`.
    """
    assert control.get_state() == "OFF"
    expect_response(host.on(), "OK", 0)

    expect_response(host.on(), "OK", 0)
    expect_response(host.status(), "STATUS ON", 0)

    control.advance_time(1.5)
    expect_response(host.on(), "OK", 0)

    control.advance_time(0.5)  # t = 2.0: only the first ON started the window
    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF"


def test_F1_AC_34_reset_clears_window(host, control):
    """F1-AC-34: RESET clears the window.

    From `OFF`, `relay-host on` prints `OK` (t = 0). After `RESET`, `relay-host on` prints `OK`
    right away, and the state is `ON`.
    """
    assert control.get_state() == "OFF"
    expect_response(host.on(), "OK", 0)

    control.reset()
    expect_response(host.on(), "OK", 0)
    assert control.get_state() == "ON"


def test_F1_AC_35_set_state_is_not_a_toggle(host, control):
    """F1-AC-35: SET_STATE is not a toggle.

    After `SET_STATE ON` at t = 0, `relay-host off` prints `OK` right away, and the state is `OFF`.
    """
    control.set_state("ON")

    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF"


def test_F1_AC_36_other_errors_take_precedence_over_busy(host, control):
    """F1-AC-36: Other errors take precedence over BUSY.

    From `OFF`, `relay-host on` prints `OK` (t = 0). Then, still at t = 0, `relay-host send "off"`
    prints `ERR UNKNOWN_CMD`, with a fault injected `relay-host off` prints `ERR FAULT`, and the
    state is still `ON`.
    """
    assert control.get_state() == "OFF"
    expect_response(host.on(), "OK", 0)

    expect_response(host.send_raw("off"), "ERR UNKNOWN_CMD", 1)
    assert control.get_state() == "ON"

    control.fault()
    expect_response(host.off(), "ERR FAULT", 1)
    assert control.get_state() == "ON"
