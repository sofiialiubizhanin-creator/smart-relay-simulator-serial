"""F1 E2E tests: interactive shell, change C1 (F1-AC-24 ... F1-AC-29).

Derived from specs/2026-11-18-relay-control/requirements.md §4.4 and §6, and validation.md
(rule V9 and the "Interactive shell (change C1)" steps). Input is piped, so no prompt is shown.
"""
from tests.e2e.helpers import expect_no_response, wait_until


def _stderr_lines(result) -> int:
    return len([line for line in result.stderr.splitlines() if line.strip()])


def _received(simulator) -> list[bytes]:
    return [data for _, direction, data in simulator.exchange_log() if direction == "RX"]


def test_F1_AC_24_shell_sends_lines_as_typed_and_prints_each_response(host, control):
    """F1-AC-24: The shell sends each line as typed and prints each response.

    From `OFF`, `relay-host shell` with the input lines `ON`, `STATUS`, `on` and an empty line
    prints exactly `OK\\nSTATUS ON\\nERR UNKNOWN_CMD\\nERR EMPTY\\n` to stdout, exits 0 at the end of
    input, and leaves the state `ON`.
    """
    assert control.get_state() == "OFF"

    result = host.shell("ON\nSTATUS\non\n\n")

    assert result.stdout == "OK\nSTATUS ON\nERR UNKNOWN_CMD\nERR EMPTY\n", f"stdout was {result.stdout!r}"
    assert result.exit_code == 0, f"exit code {result.exit_code}, stderr {result.stderr!r}"
    assert control.get_state() == "ON"


def test_F1_AC_25_no_response_does_not_end_shell_silent_device(host, control):
    """F1-AC-25: A line without a response doesn't end the shell.

    With silence on, `relay-host shell` with the input lines `STATUS` and `STATUS` prints nothing
    to stdout, prints one line to stderr for each input line (two lines), and exits 0.
    """
    control.silence()

    result = host.shell("STATUS\nSTATUS\n")

    assert result.stdout == "", f"stdout was {result.stdout!r}"
    assert _stderr_lines(result) == 2, f"stderr was {result.stderr!r}"
    assert result.exit_code == 0, f"exit code {result.exit_code}"


def test_F1_AC_25_no_response_does_not_end_shell_no_simulator(host_unreachable):
    """F1-AC-25: A line without a response doesn't end the shell.

    The same holds when no simulator is listening at the address in `RELAY_HOST_ADDRESS`:
    nothing on stdout, one stderr line per input line (two lines), exit 0.
    """
    result = host_unreachable.shell("STATUS\nSTATUS\n")

    assert result.stdout == "", f"stdout was {result.stdout!r}"
    assert _stderr_lines(result) == 2, f"stderr was {result.stderr!r}"
    assert result.exit_code == 0, f"exit code {result.exit_code}"


def test_F1_AC_26_idle_shell_does_not_block_other_clients(host, simulator):
    """F1-AC-26: An idle shell doesn't block other clients.

    A shell gets the input line `STATUS` and prints `STATUS OFF`. While it then waits for the next
    line, `relay-host status` prints `STATUS OFF` and exits 0. At end of input, the shell exits 0,
    and its whole stdout is exactly `STATUS OFF\\n`.
    """
    shell = host.open_shell()
    shell.write("STATUS\n")
    # Proof that the shell is running and has handled its line (validation.md, F1-AC-26 step 2).
    wait_until(
        lambda: b"STATUS OFF" in [data for _, d, data in simulator.exchange_log() if d == "TX"],
        timeout=10,
        message="the shell never got a response to its first line",
    )

    other = host.status()

    assert other.stdout == "STATUS OFF\n", f"other client's stdout {other.stdout!r} (stderr {other.stderr!r})"
    assert other.exit_code == 0, f"other client exited {other.exit_code}: the idle shell may hold the connection"

    result = shell.finish()
    assert result.stdout == "STATUS OFF\n", f"shell stdout was {result.stdout!r}"
    assert result.exit_code == 0, f"shell exit code {result.exit_code}, stderr {result.stderr!r}"


def test_F1_AC_27_end_of_input_ends_shell_without_sending(host, simulator):
    """F1-AC-27: End of input ends the shell without sending anything.

    `relay-host shell` with empty input prints nothing to stdout and exits 0, and the simulator
    receives nothing.
    """
    result = host.shell("")

    assert result.stdout == "", f"stdout was {result.stdout!r}"
    assert result.exit_code == 0, f"exit code {result.exit_code}, stderr {result.stderr!r}"
    assert _received(simulator) == [], f"simulator received {_received(simulator)!r}"


def test_F1_AC_28_extra_argument_to_shell_is_usage_error(host, control, simulator):
    """F1-AC-28: An extra argument to `shell` is a usage error.

    `relay-host shell ON` exits 2, prints nothing to stdout, and the simulator receives nothing.
    """
    assert control.get_state() == "OFF"

    expect_no_response(host.run("shell", "ON"), 2)
    assert control.get_state() == "OFF"
    assert _received(simulator) == [], f"simulator received {_received(simulator)!r}"


def test_F1_AC_29_leading_byte_order_mark_is_dropped(host, control, simulator):
    """F1-AC-29: A leading byte-order mark is dropped.

    From `OFF`, `relay-host shell` with input that starts with the UTF-8 byte-order mark followed by
    the lines `ON` and `STATUS` prints exactly `OK\\nSTATUS ON\\n`, exits 0, and the simulator
    receives `ON` (without the mark) and `STATUS`.
    """
    assert control.get_state() == "OFF"

    result = host.shell("\ufeffON\nSTATUS\n")  # "\ufeff" in UTF-8 is the mark EF BB BF

    assert result.stdout == "OK\nSTATUS ON\n", f"stdout was {result.stdout!r}"
    assert result.exit_code == 0, f"exit code {result.exit_code}, stderr {result.stderr!r}"
    assert _received(simulator) == [b"ON", b"STATUS"], f"simulator received {_received(simulator)!r}"
