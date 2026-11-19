"""F1 E2E tests: input errors (F1-AC-08 ... F1-AC-12).

Derived from specs/2026-11-18-relay-control/requirements.md §6 and validation.md §3.
Per validation.md V4, each rejected input starts from the state it would change if accepted.
"""
import pytest

from tests.e2e.helpers import expect_response


@pytest.mark.parametrize(
    "line, start",
    [
        ("on", "OFF"),
        ("On", "OFF"),
        ("oN", "OFF"),
        ("off", "ON"),
        ("Off", "ON"),
        ("status", "OFF"),
        ("Status", "OFF"),
    ],
)
def test_F1_AC_08_lowercase_is_rejected(host, control, line, start):
    """F1-AC-08: Lowercase is rejected.

    `relay-host send` with each of `on`, `On`, `oN`, `off`, `Off`, `status` and `Status`
    prints `ERR UNKNOWN_CMD` and exits 1. The state doesn't change.
    """
    control.set_state(start)

    expect_response(host.send_raw(line), "ERR UNKNOWN_CMD", 1)
    assert control.get_state() == start


@pytest.mark.parametrize("line", [" ON", "ON ", "ON 1", "\tSTATUS"], ids=repr)
def test_F1_AC_09_extra_whitespace_or_arguments_are_rejected(host, control, line):
    """F1-AC-09: Extra whitespace or arguments are rejected.

    `send " ON"`, `send "ON "`, `send "ON 1"` and `send "\\tSTATUS"` each print
    `ERR UNKNOWN_CMD` and exit 1. The state doesn't change.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw(line), "ERR UNKNOWN_CMD", 1)
    assert control.get_state() == "OFF"


def test_F1_AC_10_unknown_command_is_rejected(host, control):
    """F1-AC-10: Unknown commands are rejected.

    `send "TOGGLE"` prints `ERR UNKNOWN_CMD` and exits 1. The state doesn't change.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw("TOGGLE"), "ERR UNKNOWN_CMD", 1)
    assert control.get_state() == "OFF"


def test_F1_AC_10_non_ascii_line_is_rejected(host, control, simulator):
    """F1-AC-10: Unknown commands are rejected.

    `send "ÖN"` (sent as the UTF-8 bytes `C3 96 4E`) prints `ERR UNKNOWN_CMD` and exits 1.
    The state doesn't change.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw("ÖN"), "ERR UNKNOWN_CMD", 1)
    assert control.get_state() == "OFF"
    received = [data for _, direction, data in simulator.exchange_log() if direction == "RX"]
    assert received == [bytes.fromhex("C3 96 4E")], f"simulator received {received!r}"


@pytest.mark.parametrize("line", ["", "\r"], ids=repr)
def test_F1_AC_11_empty_line_is_rejected(host, control, line):
    """F1-AC-11: An empty line is rejected.

    `relay-host send ""` and `send "\\r"` print `ERR EMPTY` and exit 1. The state doesn't change.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw(line), "ERR EMPTY", 1)
    assert control.get_state() == "OFF"


@pytest.mark.parametrize(
    "line, response",
    [
        ("X" * 33, "ERR TOO_LONG"),
        ("X" * 32, "ERR UNKNOWN_CMD"),
        ("X" * 32 + "\r", "ERR UNKNOWN_CMD"),
    ],
    ids=["33_bytes", "32_bytes", "32_bytes_plus_cr"],
)
def test_F1_AC_12_line_length_limit_is_enforced(host, control, line, response):
    """F1-AC-12: The line length limit is enforced.

    From `OFF`: `send "<33 bytes>"` prints `ERR TOO_LONG` and exits 1. `send "<32 bytes>"` and
    `send "<32 bytes>\\r"` each print `ERR UNKNOWN_CMD`, not `ERR TOO_LONG`, and exit 1.
    After each, the state is still `OFF`, and `relay-host status` prints `STATUS OFF` and exits 0.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw(line), response, 1)
    assert control.get_state() == "OFF"
    expect_response(host.status(), "STATUS OFF", 0)


def test_F1_AC_12_very_long_line_gets_exactly_one_error(host, control, simulator):
    """F1-AC-12: The line length limit is enforced.

    From `OFF`: `send "<10000 bytes>"` prints `ERR TOO_LONG` and exits 1, and the simulator sends
    exactly one response for that line. The state is still `OFF`, and `relay-host status`
    prints `STATUS OFF` and exits 0.
    """
    assert control.get_state() == "OFF"

    expect_response(host.send_raw("X" * 10_000), "ERR TOO_LONG", 1)

    sent = [data for _, direction, data in simulator.exchange_log() if direction == "TX"]
    assert sent == [b"ERR TOO_LONG"], f"simulator sent {sent!r}"

    assert control.get_state() == "OFF"
    expect_response(host.status(), "STATUS OFF", 0)
