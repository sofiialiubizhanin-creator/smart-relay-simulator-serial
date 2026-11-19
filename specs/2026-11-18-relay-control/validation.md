# F1: Relay control and status - Validation

**Status:** v1.2, reviewed 2026-11-19 (v1 plus changes C1 and C2: F1-AC-24 … F1-AC-36, changed F1-AC-19).
**Phase:** 1, changed in Phase 2 by C2 (see `specs/roadmap.md`)
**Inputs:** `requirements.md` (cited as "req §N"), `plan.md`, `.claude/skills/e2e-test-conventions/` (fixture contract v1.3)

This document says how each F1 Acceptance Criterion is verified end to end, and records the results. Every expected string and exit code below is copied from `requirements.md`. If they ever differ, `requirements.md` wins and this file is fixed.

## 1. General rules

These apply to every F1 E2E test unless an AC below says otherwise.

- **V1 Start:** each test starts from the reset state (relay `OFF`, no fault, not silent). Conditions are arranged only through `control`. Relay commands are sent only through `host` (or `host_at` / `host_unreachable`).
- **V2 Response:** when the device responds, the test asserts:
  - `stdout` equals the response followed by exactly one `\n`, compared without newline translation. A `\r\n` fails.
  - The exit code is exact.
- **V3 No response:** for exit codes 2, 3 and 4, the test asserts that `stdout` is empty and `stderr` is not empty (req §4.3). The wording of `stderr` is never asserted.
- **V4 State:** whenever an AC mentions the state, the test reads it with `control.get_state()`.
  - For "the state doesn't change", the test starts from the state that the rejected input *would* change if it were accepted. For example, `on` is tried from `OFF` and `off` from `ON`.
  - Inputs that change nothing even when accepted (`status`) start from `OFF`.
- **V5 Exchange log:** `simulator.exchange_log()` is asserted only where an AC states what the simulator receives or sends. It may also be used with `wait_until` as a synchronisation step (F1-AC-16, F1-AC-26).
- **V6 Parametrisation:** each input listed in an AC is its own parametrized case.
- **V7 Timeouts:**
  - Tests use the host's default timeout.
  - `SHORT_TIMEOUT` (`"0.3"`) is used only in F1-AC-15 and F1-AC-16, to save time.
  - F1-AC-21 passes `--timeout 0.3` because the AC states that value.
  - No `sleep` is used anywhere.
  - Simulated time (the `BUSY` window, req §2.6) moves only through `control.advance_time(seconds)`. "t = x" in the steps below is that clock. Each test starts at t = 0 after the reset (V1), with no previous toggle.
- **V8 Notation:** `\r`, `\t` and `\n` mean the actual control characters (req §6). `X×N` means the letter `X` repeated N times.
- **V9 Shell (C1):**
  - Shell input is passed with `host.shell(input)` or with `host.open_shell()` and `write` / `finish`. Each input line ends with `\n`. Stdin is never a terminal, so no prompt is expected.
  - `stdout` is compared exactly, as the concatenation of the expected response lines. Each line ends with exactly one `\n`.
  - The shell's exit code is asserted exactly (req §4.4). V3 doesn't apply to the shell's exit 0.
  - Where an AC counts stderr lines, the test counts the non-empty lines of `stderr`. Their wording is never asserted.
- **V10 Regression after a change request (C2, plan D15):**
  - After a change request is implemented, the whole suite first runs **unchanged**.
  - Every failing test is recorded in validation-results.md with its file, its name, the command sequence that failed, and whether the change explains the failure.
  - Only a test whose failure the change explains may be updated, for example a quick sequence of two toggles hitting `BUSY`. An E2E test updated this way gets a `Changed:` line in its docstring that names the change.
  - Any other failure is an implementation bug and is fixed in the code, not in the test.

## 2. Timing rule (F1-AC-21)

`elapsed` is real time from starting the host process to its exit. So it includes interpreter start-up, which varies by machine. The rule therefore bounds each run from below and from above, and compares the two runs with each other so that start-up cancels out.

With run A = `relay-host status` (default timeout) and run B = `relay-host --timeout 0.3 status`, both against a silent device and both exiting 3:

| Check | Rule |
|---|---|
| T1 lower bound | `elapsed_A ≥ 1.0` and `elapsed_B ≥ 0.3` |
| T2 upper bound | `elapsed_A ≤ 2.5` and `elapsed_B ≤ 1.8` (timeout + 1.5 s start-up allowance) |
| T3 difference | `0.5 ≤ elapsed_A − elapsed_B ≤ 0.9` (nominal 0.7) |

These bounds are part of the contract. Widening them counts as weakening the test, so it needs a change to this file approved by the user.

## 3. Verification per AC

"Arrange" uses `control`, "Act" uses the host, and "Expect" follows V2–V4.

### Relay control

- **F1-AC-01**
  - Arrange: none (reset state).
  - Act: `status`.
  - Expect: `STATUS OFF`, exit 0.
- **F1-AC-02**
  - Arrange: `OFF`.
  - Act: `on`.
  - Expect: `OK`, exit 0. The state is `ON`.
- **F1-AC-03**
  - Arrange: `SET_STATE ON`.
  - Act: `off`.
  - Expect: `OK`, exit 0. The state is `OFF`.
- **F1-AC-04**
  - Arrange: `SET_STATE ON`.
  - Act: `status`.
  - Expect: `STATUS ON`, exit 0. The state is `ON`.
- **F1-AC-05**
  - Arrange: `SET_STATE ON`.
  - Act: `on`.
  - Expect: `OK`, exit 0. The state is `ON`.
- **F1-AC-06**
  - Arrange: `OFF`.
  - Act: `off`.
  - Expect: `OK`, exit 0. The state is `OFF`.
- **F1-AC-07**
  - Arrange: `OFF`.
  - Act: `send "ON\r"`, then `send "STATUS\r"`.
  - Expect: `OK`, exit 0, and the state is `ON`. Then `STATUS ON`, exit 0.

### Input errors

- **F1-AC-08**
  - Act: `send` with:
    - `on`, `On`, `oN` (from `OFF`),
    - `off`, `Off` (from `ON`),
    - `status`, `Status` (from `OFF`).
  - Expect: `ERR UNKNOWN_CMD`, exit 1. The state is unchanged.
- **F1-AC-09**
  - Arrange: `OFF`.
  - Act: `send` with `" ON"`, `"ON "`, `"ON 1"`, `"\tSTATUS"`.
  - Expect: `ERR UNKNOWN_CMD`, exit 1. The state is `OFF`.
- **F1-AC-10**
  - Arrange: `OFF`.
  - Act: `send "TOGGLE"` and `send "ÖN"`.
  - Expect: `ERR UNKNOWN_CMD`, exit 1. The state is `OFF`. For `ÖN`, the exchange log's RX entry is the bytes `C3 96 4E`.
- **F1-AC-11**
  - Arrange: `OFF`.
  - Act: `send ""` and `send "\r"`.
  - Expect: `ERR EMPTY`, exit 1. The state is `OFF`.
- **F1-AC-12**
  - Arrange: `OFF`.
  - Act and expect for each case:
    - `send X×33`: `ERR TOO_LONG`, exit 1.
    - `send X×10000`: `ERR TOO_LONG`, exit 1, and the exchange log has exactly one TX entry for this run.
    - `send X×32` and `send "X×32\r"`: `ERR UNKNOWN_CMD`, exit 1.
  - After each case: the state is `OFF`, and `status` gives `STATUS OFF`, exit 0.
  - The 10 000-byte argument is within the Windows command-line limit (32 767 characters).

### Fault, silence, reset

- **F1-AC-13**
  - Arrange: `FAULT ON`, with the start state chosen per V4.
  - Act and start state:
    - `on` (from `OFF`),
    - `off` (from `ON`),
    - `status`, `send "TOGGLE"`, `send ""`, `send X×33` (from `OFF`).
  - Expect: `ERR FAULT`, exit 1. The state is unchanged.
- **F1-AC-14**
  - Arrange: `SET_STATE ON`, `FAULT ON`, `FAULT OFF`.
  - Expect:
    - The state is `ON`.
    - `status` gives `STATUS ON`, exit 0.
    - `off` gives `OK`, exit 0, and the state becomes `OFF`.
- **F1-AC-15**
  - Arrange: `OFF`, `SILENCE ON`. A second case also adds `FAULT ON`.
  - Act: `run("--timeout", SHORT_TIMEOUT, "on")`.
  - Expect: exit 3 and V3. The state is `OFF`.
- **F1-AC-16**
  - Arrange: `OFF`, `SILENCE ON`.
  - Act:
    1. `run("--timeout", SHORT_TIMEOUT, "on")`. Expect exit 3.
    2. `wait_until` the exchange log has an RX entry `ON`, so the line was received while silent.
    3. `SILENCE OFF`.
  - Expect: the state is `OFF`, and `status` gives `STATUS OFF`, exit 0.
- **F1-AC-17**
  - Arrange: `SET_STATE ON`, `FAULT ON`, `SILENCE ON`, then `RESET`.
  - Act: `status`.
  - Expect: `STATUS OFF`, exit 0. The state is `OFF`.

### Host CLI

- **F1-AC-18**
  - Arrange: `SET_STATE ON`.
  - Act: `send "STATUS"` and `status`.
  - Expect: the same stdout (`STATUS ON\n`) and exit code (0).
  - Then from `OFF`: `send "on"` gives `ERR UNKNOWN_CMD`, exit 1, and the state is `OFF`.
- **F1-AC-19**: one case per response:

  | Response | Arrange | Act | Exit |
  |---|---|---|---|
  | `OK` | `OFF` | `on` | 0 |
  | `STATUS ON` | `SET_STATE ON` | `status` | 0 |
  | `STATUS OFF` | `OFF` | `status` | 0 |
  | `ERR UNKNOWN_CMD` | `OFF` | `send "TOGGLE"` | 1 |
  | `ERR EMPTY` | `OFF` | `send ""` | 1 |
  | `ERR TOO_LONG` | `OFF` | `send X×33` | 1 |
  | `ERR FAULT` | `FAULT ON` | `status` | 1 |
  | `ERR BUSY` | `host.on()` at t = 0 (a toggle; `SET_STATE` doesn't start the window) | `off` at t = 0 | 1 |

  stdout is exactly the response plus one `\n` (V2). The `ERR BUSY` row was added by change C2.
- **F1-AC-20**
  - Arrange: `OFF`.
  - Act with `run(...)`:
    - `"toggle"` (unknown subcommand),
    - `"send"` (missing argument),
    - `"on", "extra"` (extra argument),
    - `"send", "ON\nOFF"`,
    - `"--timeout", v, "on"` for v in `0`, `-1`, `abc`, `nan`.
  - Expect: exit 2 and V3. The state is `OFF`, and the exchange log has no RX entry.
- **F1-AC-21**
  - Arrange: `SILENCE ON`.
  - Act: `run("status")` and `run("--timeout", "0.3", "status")`.
  - Expect: both exit 3 with V3, and the timing rule in §2 holds.
- **F1-AC-22**
  - Act: `host_unreachable.status()`.
  - Expect: exit 4 and V3.
- **F1-AC-23**
  - Act: `host_at(value).status()` for `127.0.0.1`, `127.0.0.1:abc`, `127.0.0.1:0` and an empty string.
  - Expect: exit 4 and V3.
  - If the platform drops an empty environment variable before the host sees it, the empty-string case would test "unset" instead. In that case, raise a spec question; don't change the test.

### Interactive shell (change C1)

- **F1-AC-24**
  - Arrange: `OFF`.
  - Act: `host.shell("ON\nSTATUS\non\n\n")`. That is four lines: `ON`, `STATUS`, `on` and an empty line.
  - Expect: stdout is exactly `OK\nSTATUS ON\nERR UNKNOWN_CMD\nERR EMPTY\n`, exit 0, and the state is `ON`.
- **F1-AC-25**: two cases.
  - Silent device:
    - Arrange: `SILENCE ON`.
    - Act: `host.shell("STATUS\nSTATUS\n")`.
  - No simulator:
    - Act: `host_unreachable.shell("STATUS\nSTATUS\n")`.
  - Expect (both cases): stdout is empty, stderr has exactly 2 non-empty lines, and exit 0.
  - Duration: the default 1.0 s timeout applies (V7), so the silent case takes about 2 s. On Windows, the no-simulator case takes about 4 s (2 s per refused connection).
- **F1-AC-26**
  - Act:
    1. `s = host.open_shell()`, then `s.write("STATUS\n")`.
    2. `wait_until` the exchange log has a TX entry `STATUS OFF`. The shell is now running and waiting for its next line.
    3. `host.status()`.
    4. `s.finish()`.
  - Expect:
    - Step 3 gives `STATUS OFF`, exit 0.
    - Step 4 gives exit 0, and the shell's whole stdout is exactly `STATUS OFF\n`.
  - Step 3 must succeed within the host's default timeout. A shell that held the connection would make it exit 3 instead.
- **F1-AC-27**
  - Act: `host.shell("")`.
  - Expect: stdout is empty, exit 0, and the exchange log has no RX entry.
- **F1-AC-28**
  - Act: `host.run("shell", "ON")`.
  - Expect: exit 2 and V3. The state is `OFF`, and the exchange log has no RX entry.
- **F1-AC-29**
  - Arrange: `OFF`.
  - Act: `host.shell("﻿ON\nSTATUS\n")`. `﻿` written as UTF-8 is the byte-order mark `EF BB BF`.
  - Expect:
    - stdout is exactly `OK\nSTATUS ON\n`, exit 0.
    - The exchange log's RX entries are exactly `ON` and `STATUS`, with no mark bytes.

### Toggle rate limit (change C2)

In every step below, "t = x" means `control.advance_time` has moved the clock to x seconds since the test's reset (V7).

- **F1-AC-30**
  - Act: `on` (t = 0), then `advance_time(1.9)`, then `off`.
  - Expect: `on` gives `OK`, exit 0. `off` gives `ERR BUSY`, exit 1. The state is `ON`.
- **F1-AC-31**
  - Act: `on` (t = 0), then `advance_time(2.0)`, then `off`.
  - Expect: `off` gives `OK`, exit 0. The state is `OFF`.
- **F1-AC-32**
  - Act: `on` (t = 0); `advance_time(1.5)` and `off`; `advance_time(0.5)` (t = 2.0) and `off`.
  - Expect: the first `off` gives `ERR BUSY`, exit 1, with the state `ON`. The second `off` gives `OK`, exit 0, with the state `OFF`.
- **F1-AC-33**
  - Act:
    1. `on` (t = 0), then `on` and `status`, still at t = 0.
    2. `advance_time(1.5)` and `on`.
    3. `advance_time(0.5)` (t = 2.0) and `off`.
  - Expect: the second and third `on` give `OK`; `status` gives `STATUS ON`; each exits 0. The final `off` gives `OK`, exit 0, with the state `OFF`.
- **F1-AC-34**
  - Act: `on` (t = 0); `control.reset()`; `on`.
  - Expect: the second `on` gives `OK`, exit 0, and the state is `ON`.
- **F1-AC-35**
  - Act: `control.set_state("ON")` (t = 0), then `off`.
  - Expect: `off` gives `OK`, exit 0, and the state is `OFF`.
- **F1-AC-36**
  - Act: `on` (t = 0). Still at t = 0: `send "off"`; then `control.fault()` and `off`.
  - Expect: `send "off"` gives `ERR UNKNOWN_CMD`, exit 1. The faulted `off` gives `ERR FAULT`, exit 1. The state is `ON` throughout.

## 4. Scenario coverage

| Kind | ACs |
|---|---|
| Positive | F1-AC-01, 02, 03, 04, 07, 14, 17, 18, 19, 24, 26, 31 |
| Negative | F1-AC-08, 09, 10, 11, 20, 22 (no simulator), 23, 24 (lowercase and empty line in the shell), 28, 30 (toggle too soon), 32 (retry too soon) |
| Edge | F1-AC-05, 06, 07, 12, 27, 29, 31 (exactly 2.0 s), 33, 34, 35 |
| Fault injection (control API) | F1-AC-13, 14, 15, 16, 17, 21, 25, 36 |
| Controlled time (control API) | F1-AC-30, 31, 32, 33 |

The negative and fault cases required by the roadmap:
- Unknown command: F1-AC-10.
- Lowercase: F1-AC-08.
- Empty line: F1-AC-11.
- Repeated `ON`: F1-AC-05.
- Silent device: F1-AC-15.

**Not verified end to end** (req §2.4, §4.3, §7):
- Bounded memory for very long lines (a design constraint).
- A connection closed before `\n`.
- The wording of stderr messages.
- Shell prompt `relay> ` and Ctrl+C. Both need a real terminal, so they are checked by hand (plan 12.7) and recorded in validation-results.md.
- `relay-sim` following real time (req §2.6). E2E tests must not wait in real time, so this is checked by hand (plan 13.9) and recorded in validation-results.md. The real-time clock itself has component tests that use a fake time source.

## Traceability

| AC ID    | Test(s) | Notes |
|----------|---------|-------|
| F1-AC-01 | tests/e2e/test_f1_relay_control.py::test_F1_AC_01_initial_state_is_off | positive |
| F1-AC-02 | tests/e2e/test_f1_relay_control.py::test_F1_AC_02_on_turns_relay_on | positive |
| F1-AC-03 | tests/e2e/test_f1_relay_control.py::test_F1_AC_03_off_turns_relay_off | positive |
| F1-AC-04 | tests/e2e/test_f1_relay_control.py::test_F1_AC_04_status_reports_state_without_changing_it | positive |
| F1-AC-05 | tests/e2e/test_f1_relay_control.py::test_F1_AC_05_repeated_on_is_accepted_and_changes_nothing | edge (repeated ON) |
| F1-AC-06 | tests/e2e/test_f1_relay_control.py::test_F1_AC_06_repeated_off_is_accepted_and_changes_nothing | edge (repeated OFF) |
| F1-AC-07 | tests/e2e/test_f1_relay_control.py::test_F1_AC_07_trailing_cr_is_ignored | edge (trailing CR) |
| F1-AC-08 | tests/e2e/test_f1_input_errors.py::test_F1_AC_08_lowercase_is_rejected | negative (lowercase) |
| F1-AC-09 | tests/e2e/test_f1_input_errors.py::test_F1_AC_09_extra_whitespace_or_arguments_are_rejected | negative (whitespace, arguments) |
| F1-AC-10 | tests/e2e/test_f1_input_errors.py::test_F1_AC_10_non_ascii_line_is_rejected<br>tests/e2e/test_f1_input_errors.py::test_F1_AC_10_unknown_command_is_rejected | negative (unknown, non-ASCII) |
| F1-AC-11 | tests/e2e/test_f1_input_errors.py::test_F1_AC_11_empty_line_is_rejected | negative (empty line) |
| F1-AC-12 | tests/e2e/test_f1_input_errors.py::test_F1_AC_12_line_length_limit_is_enforced<br>tests/e2e/test_f1_input_errors.py::test_F1_AC_12_very_long_line_gets_exactly_one_error | edge (32 / 32+CR / 33 / 10 000 bytes) |
| F1-AC-13 | tests/e2e/test_f1_fault_silence_reset.py::test_F1_AC_13_faulted_device_rejects_everything | fault injection |
| F1-AC-14 | tests/e2e/test_f1_fault_silence_reset.py::test_F1_AC_14_clearing_fault_restores_normal_operation | fault injection |
| F1-AC-15 | tests/e2e/test_f1_fault_silence_reset.py::test_F1_AC_15_silent_device_does_not_respond | fault injection (silent, silent + fault) |
| F1-AC-16 | tests/e2e/test_f1_fault_silence_reset.py::test_F1_AC_16_ending_silence_restores_operation_without_replay | fault injection (no replay) |
| F1-AC-17 | tests/e2e/test_f1_fault_silence_reset.py::test_F1_AC_17_reset_restores_initial_condition | fault injection (reset) |
| F1-AC-18 | tests/e2e/test_f1_host_cli.py::test_F1_AC_18_send_delivers_the_line_unchanged | positive (send transparency) |
| F1-AC-19 | tests/e2e/test_f1_host_cli.py::test_F1_AC_19_output_is_the_device_response_unchanged | positive (output format); changed by C2 (`ERR BUSY` case) |
| F1-AC-20 | tests/e2e/test_f1_host_cli.py::test_F1_AC_20_usage_errors_exit_2_and_send_nothing | negative (usage errors) |
| F1-AC-21 | tests/e2e/test_f1_host_cli.py::test_F1_AC_21_timeout_defaults_to_1s_and_can_be_configured | timeout, timing rule §2 |
| F1-AC-22 | tests/e2e/test_f1_host_cli.py::test_F1_AC_22_connection_failure_exits_4 | connection failure |
| F1-AC-23 | tests/e2e/test_f1_host_cli.py::test_F1_AC_23_invalid_address_exits_4 | negative (invalid address) |
| F1-AC-24 | tests/e2e/test_f1_host_shell.py::test_F1_AC_24_shell_sends_lines_as_typed_and_prints_each_response | positive, negative (shell: lines as typed) — C1 |
| F1-AC-25 | tests/e2e/test_f1_host_shell.py::test_F1_AC_25_no_response_does_not_end_shell_no_simulator<br>tests/e2e/test_f1_host_shell.py::test_F1_AC_25_no_response_does_not_end_shell_silent_device | fault injection (shell: no response, no simulator) — C1 |
| F1-AC-26 | tests/e2e/test_f1_host_shell.py::test_F1_AC_26_idle_shell_does_not_block_other_clients | positive (shell doesn't block other clients) — C1 |
| F1-AC-27 | tests/e2e/test_f1_host_shell.py::test_F1_AC_27_end_of_input_ends_shell_without_sending | edge (shell: empty input) — C1 |
| F1-AC-28 | tests/e2e/test_f1_host_shell.py::test_F1_AC_28_extra_argument_to_shell_is_usage_error | negative (shell: usage error) — C1 |
| F1-AC-29 | tests/e2e/test_f1_host_shell.py::test_F1_AC_29_leading_byte_order_mark_is_dropped | edge (shell: leading byte-order mark from PowerShell) — C1 |
| F1-AC-30 | tests/e2e/test_f1_busy.py::test_F1_AC_30_toggle_within_2s_is_rejected | negative (toggle at t = 1.9 → BUSY) — C2 |
| F1-AC-31 | tests/e2e/test_f1_busy.py::test_F1_AC_31_toggle_exactly_2s_later_is_accepted | edge (toggle at exactly t = 2.0 → OK) — C2 |
| F1-AC-32 | tests/e2e/test_f1_busy.py::test_F1_AC_32_rejected_toggle_does_not_restart_window | negative (rejected toggle doesn't restart the window) — C2 |
| F1-AC-33 | tests/e2e/test_f1_busy.py::test_F1_AC_33_non_toggles_never_busy_and_keep_window | edge (non-toggles never BUSY, window unchanged) — C2 |
| F1-AC-34 | tests/e2e/test_f1_busy.py::test_F1_AC_34_reset_clears_window | edge (RESET clears the window) — C2 |
| F1-AC-35 | tests/e2e/test_f1_busy.py::test_F1_AC_35_set_state_is_not_a_toggle | edge (SET_STATE is not a toggle) — C2 |
| F1-AC-36 | tests/e2e/test_f1_busy.py::test_F1_AC_36_other_errors_take_precedence_over_busy | fault injection (other errors take precedence over BUSY) — C2 |

## Results

Results are recorded in [validation-results.md](validation-results.md) (decided 2026-11-19):
- §1 Mutation check (2026-11-19): 15 of 15 planted bugs caught.
- §2 Validation run (2026-11-19, commit `e8f7acb`): 262 passed, 23/23 ACs covered, checker clean.
- §3 Shell hand check, change C1 (2026-11-19): prompt, end of input and Ctrl+C all as expected.
- §4 Validation run including C1 (2026-11-19): 286 passed, 29/29 ACs covered, checker clean. The shell mutation check was skipped by the user's decision.
- §5 Regression run after C2 (2026-11-19, rule V10): 4 component tests fail, all explained by C2 (quick toggle sequences); all E2E tests pass unchanged.
- §6 `relay-sim` real-time hand check, C2 (2026-11-19): all as expected.
- §7 Final validation run, Phase 2 (2026-11-19, commit `7dfb858`): 317 passed, 36/36 ACs covered, checker clean.
