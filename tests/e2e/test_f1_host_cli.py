"""F1 E2E tests: host CLI (F1-AC-18 ... F1-AC-23).

Derived from specs/2026-11-18-relay-control/requirements.md §6 and validation.md §2-§3.
"""
import pytest

from tests.e2e.helpers import expect_no_response, expect_response


def test_F1_AC_18_send_delivers_the_line_unchanged(host, control):
    """F1-AC-18: `send` delivers the line unchanged.

    `relay-host send "STATUS"` gives the same stdout and exit code as `relay-host status`.
    `send "on"` gets `ERR UNKNOWN_CMD`, not `OK`, which shows that the host didn't change the case.
    """
    control.set_state("ON")
    via_send = host.send_raw("STATUS")
    via_status = host.status()
    expect_response(via_send, "STATUS ON", 0)
    assert (via_send.stdout, via_send.exit_code) == (via_status.stdout, via_status.exit_code)

    control.set_state("OFF")
    expect_response(host.send_raw("on"), "ERR UNKNOWN_CMD", 1)
    assert control.get_state() == "OFF"


@pytest.mark.parametrize(
    "arrange, act, response, exit_code",
    [
        (lambda c: None, lambda h: h.on(), "OK", 0),
        (lambda c: c.set_state("ON"), lambda h: h.status(), "STATUS ON", 0),
        (lambda c: None, lambda h: h.status(), "STATUS OFF", 0),
        (lambda c: None, lambda h: h.send_raw("TOGGLE"), "ERR UNKNOWN_CMD", 1),
        (lambda c: None, lambda h: h.send_raw(""), "ERR EMPTY", 1),
        (lambda c: None, lambda h: h.send_raw("X" * 33), "ERR TOO_LONG", 1),
        (lambda c: c.fault(), lambda h: h.status(), "ERR FAULT", 1),
    ],
    ids=["OK", "STATUS_ON", "STATUS_OFF", "ERR_UNKNOWN_CMD", "ERR_EMPTY", "ERR_TOO_LONG", "ERR_FAULT"],
)
def test_F1_AC_19_output_is_the_device_response_unchanged(host, control, arrange, act, response, exit_code):
    """F1-AC-19: The output is the device response, unchanged.

    For each device response, stdout is exactly that response followed by one `\\n`.
    The exit code is 0 for `OK` and `STATUS …`, and 1 for `ERR …`.
    """
    arrange(control)

    expect_response(act(host), response, exit_code)


@pytest.mark.parametrize(
    "args",
    [
        ("toggle",),
        ("send",),
        ("on", "extra"),
        ("send", "ON\nOFF"),
        ("--timeout", "0", "on"),
        ("--timeout", "-1", "on"),
        ("--timeout", "abc", "on"),
        ("--timeout", "nan", "on"),
    ],
    ids=[
        "unknown_subcommand", "missing_send_argument", "extra_argument", "send_line_with_newline",
        "timeout_0", "timeout_negative", "timeout_non_numeric", "timeout_nan",
    ],
)
def test_F1_AC_20_usage_errors_exit_2_and_send_nothing(host, control, simulator, args):
    """F1-AC-20: Usage errors exit 2 and send nothing.

    Each usage error exits 2, prints nothing to stdout, and leaves the state unchanged,
    and the simulator receives nothing.
    """
    assert control.get_state() == "OFF"

    expect_no_response(host.run(*args), 2)
    assert control.get_state() == "OFF"
    received = [data for _, direction, data in simulator.exchange_log() if direction == "RX"]
    assert received == [], f"simulator received {received!r}"


def test_F1_AC_21_timeout_defaults_to_1s_and_can_be_configured(host, control):
    """F1-AC-21: The timeout defaults to 1.0 s and can be configured.

    Against a silent device, `relay-host status` with no `--timeout` exits 3 after 1.0 s, and
    `relay-host --timeout 0.3 status` exits 3 after 0.3 s, within the tolerance in validation.md §2.
    """
    control.silence()

    default = host.run("status")
    configured = host.run("--timeout", "0.3", "status")

    expect_no_response(default, 3)
    expect_no_response(configured, 3)
    a, b = default.elapsed, configured.elapsed
    # validation.md §2: T1 lower bounds, T2 upper bounds, T3 difference (start-up cancels out).
    assert a >= 1.0 and b >= 0.3, f"T1: elapsed {a:.3f} s / {b:.3f} s"
    assert a <= 2.5 and b <= 1.8, f"T2: elapsed {a:.3f} s / {b:.3f} s"
    assert 0.5 <= a - b <= 0.9, f"T3: difference {a - b:.3f} s (elapsed {a:.3f} s / {b:.3f} s)"


def test_F1_AC_22_connection_failure_exits_4(host_unreachable):
    """F1-AC-22: A connection failure exits 4.

    When no simulator is listening at the address in `RELAY_HOST_ADDRESS`, `relay-host status`
    exits 4 and prints nothing to stdout.
    """
    expect_no_response(host_unreachable.status(), 4)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "127.0.0.1:abc", "127.0.0.1:0", ""],
    ids=["no_port", "port_not_a_number", "port_0", "empty"],
)
def test_F1_AC_23_invalid_address_exits_4(host_at, address):
    """F1-AC-23: An invalid address exits 4.

    With `RELAY_HOST_ADDRESS` set to `127.0.0.1` (no port), `127.0.0.1:abc`, `127.0.0.1:0` or an
    empty string, `relay-host status` exits 4 and prints nothing to stdout.
    """
    expect_no_response(host_at(address).status(), 4)
