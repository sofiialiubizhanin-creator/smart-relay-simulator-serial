"""F1 E2E tests: fault, silence, reset (F1-AC-13 ... F1-AC-17).

Derived from specs/2026-11-18-relay-control/requirements.md §6 and validation.md §3.
Faults and silence are injected only through the control API.
"""
import pytest

from tests.e2e.helpers import SHORT_TIMEOUT, expect_no_response, expect_response, wait_until


@pytest.mark.parametrize(
    "act, start",
    [
        (lambda host: host.on(), "OFF"),
        (lambda host: host.off(), "ON"),
        (lambda host: host.status(), "OFF"),
        (lambda host: host.send_raw("TOGGLE"), "OFF"),
        (lambda host: host.send_raw(""), "OFF"),
        (lambda host: host.send_raw("X" * 33), "OFF"),
    ],
    ids=["on", "off", "status", "send_unknown", "send_empty", "send_too_long"],
)
def test_F1_AC_13_faulted_device_rejects_everything(host, control, act, start):
    """F1-AC-13: A faulted device rejects everything.

    With a fault injected, `on`, `off`, `status`, and `send` with `TOGGLE`, an empty line or
    `<33 bytes>` each print `ERR FAULT` and exit 1. The state doesn't change.
    """
    control.set_state(start)
    control.fault()

    expect_response(act(host), "ERR FAULT", 1)
    assert control.get_state() == start


def test_F1_AC_14_clearing_fault_restores_normal_operation(host, control):
    """F1-AC-14: Clearing the fault restores normal operation.

    From `ON`, after `FAULT ON` then `FAULT OFF`: the state is still `ON`; `relay-host status`
    prints `STATUS ON` and exits 0; `relay-host off` prints `OK` and exits 0, and the state
    becomes `OFF`.
    """
    control.set_state("ON")
    control.fault()
    control.fault(False)

    assert control.get_state() == "ON"
    expect_response(host.status(), "STATUS ON", 0)
    expect_response(host.off(), "OK", 0)
    assert control.get_state() == "OFF"


@pytest.mark.parametrize("also_faulted", [False, True], ids=["silent", "silent_and_faulted"])
def test_F1_AC_15_silent_device_does_not_respond(host, control, also_faulted):
    """F1-AC-15: A silent device doesn't respond.

    With silence on, `relay-host on` prints nothing to stdout and exits 3 once the timeout
    passes. The state doesn't change. The same holds when a fault is also injected
    (silence wins, req §2.5).
    """
    control.silence()
    if also_faulted:
        control.fault()

    result = host.run("--timeout", SHORT_TIMEOUT, "on")

    expect_no_response(result, 3)
    assert control.get_state() == "OFF"


def test_F1_AC_16_ending_silence_restores_operation_without_replay(host, control, simulator):
    """F1-AC-16: Ending silence restores operation without replay.

    From `OFF` with silence on, `relay-host on` exits 3. After `SILENCE OFF`, the state is still
    `OFF` (the `ON` was never executed), and `relay-host status` prints `STATUS OFF` and exits 0.
    """
    control.silence()

    expect_no_response(host.run("--timeout", SHORT_TIMEOUT, "on"), 3)
    # Make sure the line really arrived while the device was silent before ending silence.
    wait_until(
        lambda: (b"ON" in [data for _, d, data in simulator.exchange_log() if d == "RX"]),
        timeout=2,
        message="the simulator never received the ON sent while silent",
    )
    control.silence(False)

    assert control.get_state() == "OFF"
    expect_response(host.status(), "STATUS OFF", 0)


def test_F1_AC_17_reset_restores_initial_condition(host, control):
    """F1-AC-17: Reset restores the initial condition.

    After `RESET`, starting from state `ON` with fault and silence active, `relay-host status`
    prints `STATUS OFF` and exits 0.
    """
    control.set_state("ON")
    control.fault()
    control.silence()
    control.reset()

    expect_response(host.status(), "STATUS OFF", 0)
    assert control.get_state() == "OFF"
