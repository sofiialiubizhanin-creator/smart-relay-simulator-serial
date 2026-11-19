# F1: Relay control and status - Validation

**Status:** v1, draft for review.
**Phase:** 1 (see `specs/roadmap.md`)
**Inputs:** `requirements.md` (cited as "req §N"), `plan.md`, `.claude/skills/e2e-test-conventions/` (fixture contract v1.2)

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
- **V5 Exchange log:** `simulator.exchange_log()` is asserted only where an AC states what the simulator receives or sends. It may also be used with `wait_until` as a synchronisation step (F1-AC-16).
- **V6 Parametrisation:** each input listed in an AC is its own parametrized case.
- **V7 Timeouts:**
  - Tests use the host's default timeout.
  - `SHORT_TIMEOUT` (`"0.3"`) is used only in F1-AC-15 and F1-AC-16, to save time.
  - F1-AC-21 passes `--timeout 0.3` because the AC states that value.
  - No `sleep` is used anywhere.
- **V8 Notation:** `\r`, `\t` and `\n` mean the actual control characters (req §6). `X×N` means the letter `X` repeated N times.

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

  stdout is exactly the response plus one `\n` (V2).
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

## 4. Scenario coverage

| Kind | ACs |
|---|---|
| Positive | F1-AC-01, 02, 03, 04, 07, 14, 17, 18, 19 |
| Negative | F1-AC-08, 09, 10, 11, 20, 23 |
| Edge | F1-AC-05, 06, 07, 12 |
| Fault injection (control API) | F1-AC-13, 14, 15, 16, 17, 21, 22 |

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

## Traceability

| AC ID    | Test(s) | Notes |
|----------|---------|-------|
| F1-AC-01 |  | positive |
| F1-AC-02 |  | positive |
| F1-AC-03 |  | positive |
| F1-AC-04 |  | positive |
| F1-AC-05 |  | edge (repeated ON) |
| F1-AC-06 |  | edge (repeated OFF) |
| F1-AC-07 |  | edge (trailing CR) |
| F1-AC-08 |  | negative (lowercase) |
| F1-AC-09 |  | negative (whitespace, arguments) |
| F1-AC-10 |  | negative (unknown, non-ASCII) |
| F1-AC-11 |  | negative (empty line) |
| F1-AC-12 |  | edge (32 / 32+CR / 33 / 10 000 bytes) |
| F1-AC-13 |  | fault injection |
| F1-AC-14 |  | fault injection |
| F1-AC-15 |  | fault injection (silent, silent + fault) |
| F1-AC-16 |  | fault injection (no replay) |
| F1-AC-17 |  | fault injection (reset) |
| F1-AC-18 |  | positive (send transparency) |
| F1-AC-19 |  | positive (output format) |
| F1-AC-20 |  | negative (usage errors) |
| F1-AC-21 |  | timeout, timing rule §2 |
| F1-AC-22 |  | connection failure |
| F1-AC-23 |  | negative (invalid address) |

## Results

Not run yet. Filled in by plan task 9.5 with the date, commit, pass count and any open spec questions.
