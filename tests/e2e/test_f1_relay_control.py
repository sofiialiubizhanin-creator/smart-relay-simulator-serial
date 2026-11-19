"""F1 E2E tests: relay control (F1-AC-01 ... F1-AC-07).

Derived from specs/2026-11-18-relay-control/requirements.md §6 and validation.md §3.
"""
from tests.e2e.helpers import expect_response


def test_F1_AC_01_initial_state_is_off(host):
    """F1-AC-01: Initial state is OFF.

    After the simulator starts or is reset, `relay-host status` prints `STATUS OFF` and exits 0.
    """
    result = host.status()

    assert result.stdout == "STATUS OFF\n", f"stdout was {result.stdout!r}"
    assert result.exit_code == 0, f"exit code {result.exit_code}, stderr {result.stderr!r}"


def test_F1_AC_02_on_turns_relay_on(host, control):
    """F1-AC-02: ON turns the relay on.

    From `OFF`, `relay-host on` prints `OK` and exits 0. The state is `ON`.
    """
    assert control.get_state() == "OFF"

    expect_response(host.on(), "OK", 0)
    assert control.get_state() == "ON"


def test_F1_AC_03_off_turns_relay_off(host, control):
    """F1-AC-03: OFF turns the relay off.

    From `ON`, `relay-host off` prints `OK` and exits 0. The state is `OFF`.
    """
    control.set_state("ON")

    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF"


def test_F1_AC_04_status_reports_state_without_changing_it(host, control):
    """F1-AC-04: STATUS reports the state without changing it.

    When the state is `ON`, `relay-host status` prints `STATUS ON` and exits 0. The state is still `ON`.
    """
    control.set_state("ON")

    expect_response(host.status(), "STATUS ON", 0)
    assert control.get_state() == "ON"


def test_F1_AC_05_repeated_on_is_accepted_and_changes_nothing(host, control):
    """F1-AC-05: Repeated ON is accepted and changes nothing.

    When the state is `ON`, `relay-host on` prints `OK` and exits 0. The state is still `ON`.
    """
    control.set_state("ON")

    expect_response(host.on(), "OK", 0)
    assert control.get_state() == "ON"


def test_F1_AC_06_repeated_off_is_accepted_and_changes_nothing(host, control):
    """F1-AC-06: Repeated OFF is accepted and changes nothing.

    When the state is `OFF`, `relay-host off` prints `OK` and exits 0. The state is still `OFF`.
    """
    assert control.get_state() == "OFF"

    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF"


def test_F1_AC_07_trailing_cr_is_ignored(host, control):
    """F1-AC-07: A trailing CR is ignored.

    From `OFF`, `relay-host send "ON\\r"` prints `OK`, exits 0, and the state is `ON`.
    Then `relay-host send "STATUS\\r"` prints `STATUS ON` and exits 0.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw("ON\r"), "OK", 0)
    assert control.get_state() == "ON"

    expect_response(host.send_raw("STATUS\r"), "STATUS ON", 0)
