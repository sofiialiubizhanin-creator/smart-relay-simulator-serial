# F1: Relay control and status - Plan

**Status:** v1.1, reviewed 2026-11-19 (v1 plus §12 for requirements change C1).
**Phase:** 1 (see `specs/roadmap.md`)
**Inputs:** `requirements.md` (this folder, cited as "req §N"), `specs/mission.md`, `specs/tech-stack.md`, `.claude/skills/e2e-test-conventions/`

This plan says *how* F1 is built and in what order. It doesn't add or change behaviour: anything observable is defined in `requirements.md`. If the two disagree, `requirements.md` wins and the plan gets fixed. Section numbers without "req" refer to this plan.

Phase 1 is done when every F1 AC (F1-AC-01 … F1-AC-29, including change C1) is covered by an E2E test that references it, `pytest` runs the whole suite green with one command, the negative and fault-injection cases are included, a CHANGELOG.md entry for Phase 1 is added, and README.md explains how to run the program and all tests with one command (roadmap, Phase 1).

---

## 0. Decisions

All decisions were accepted in review on 2026-11-19.

| ID | Decision |
|---|---|
| D1 | **Host address:** environment variable only (req §4.1). CLI form: `relay-host [--timeout S] on\|off\|status\|send <line>\|shell` (`shell`: §12). |
| D2 | **Simulator ports:** serial `5555`, control `5556`, bound to `127.0.0.1`. Started manually with `relay-sim [--bind ADDR] [--port N] [--control-port N]`. Port `0` means "pick a free port", which the tests use. |
| D3 | **Control API wire format:** see §0.1. |
| D4 | *Removed: the dropped-connection case is out of scope (req §8).* |
| D5 | **Non-ASCII input:** the host sends the `send` argument as UTF-8 bytes (req §4.2). The simulator rejects any byte above `0x7F` (req §2.1, §3). |
| D6 | **Test topology:** the simulator runs in-process on a background thread (ports `0`). The `host` fixture runs the real `relay-host` CLI as a subprocess (`sys.executable -m relay_host`), because the ACs are stated as CLI stdout and exit codes. |
| D7 | **Connections:** the serial server handles one connection at a time (several hosts are out of scope, req §8). The control server runs on its own thread. A single lock guards the relay state, fault, silence and clock. |
| D8 | **Exchange log:** the simulator records every received line and sent response with a timestamp and direction (`RX`/`TX`). The `host` fixture records each CLI run with start and end timestamps, argv, exit code, stdout and stderr. Both go into the pytest-html report (`reports/report.html`) for each test, and the same entries are appended as plain text to `reports/exchange.log` under a header with the test's node ID. Both files are overwritten on each `pytest` run. |

### 0.1 Control API wire format (D3)

- A TCP connection to the control port. ASCII, one command per line ending in `\n` (a trailing `\r` is stripped), one response line per command.
- Several commands can be sent on one connection.

| Command | Success response | Notes |
|---|---|---|
| `SET_STATE ON` / `SET_STATE OFF` | `OK` | |
| `FAULT ON` / `FAULT OFF` | `OK` | `FAULT OFF` keeps the relay state |
| `SILENCE ON` / `SILENCE OFF` | `OK` | Lines received while silent are dropped |
| `RESET` | `OK` | Relay `OFF`, fault off, silence off, clock back to 0, exchange log cleared |
| `ADVANCE_TIME <sec>` | `OK` | `<sec>` is a non-negative decimal number |
| `GET_STATE` | `ON` or `OFF` | |
| anything else / bad argument | `ERR <reason>` | Control errors only matter to tests. They never reach the host |

---

## 1. Project scaffolding

Scaffolding adds no behaviour, so it may be done before §2.

1.1 Add `pyproject.toml`:
   - Python `>=3.11`, package sources under `src/`, runtime dependency `pyserial`.
   - Test dependencies `pytest` and `pytest-html`, as an optional `test` extra.
   - Console scripts `relay-host = relay_host.cli:main` and `relay-sim = relay_sim.__main__:main`.
1.2 Create the layout:
```
src/relay_sim/      __init__.py, __main__.py, clock.py, relay.py, protocol.py, server.py, control.py, exchange_log.py, simulator.py
src/relay_host/     __init__.py, __main__.py, client.py, cli.py
tests/e2e/          __init__.py, conftest.py, helpers.py, test_f1_*.py
tests/unit/         __init__.py, test_*.py   (component checks for §3–§6; not AC coverage)
```
1.3 Configure pytest in `pyproject.toml`:
   - `testpaths = ["tests"]`, `pythonpath = ["src", "."]`.
   - `addopts = "--html=reports/report.html --self-contained-html -p pytester"` (`pytester` is needed by 7.4).
   - Plain `pytest` from the repo root must work with no other step after installing dependencies.
1.4 Add `.gitignore` entries for `reports/`, `__pycache__/`, `*.egg-info/`, `.venv/`.
1.5 `README.md` explains how to set up, run the program (`relay-sim`, `relay-host`) and run all tests with one command (`pytest`). Keep it current whenever commands change (roadmap: every phase).

**Done when:** `pip install -e .[test]` succeeds and `pytest` runs (no tests collected yet) and writes `reports/report.html`.

---

## 2. Contract and validation documents (before implementation)

2.1 Review the requirements. *Done 2026-11-19.*
2.2 Align the fixture contract (`.claude/skills/e2e-test-conventions/references/fixtures-and-control-api.md`) with F1. *Done 2026-11-19, reference v1.2.* It covers:
   - `control.fault(enabled)` instead of a named fault.
   - `HostResult` fields: `exit_code`, `stdout`, `stderr`, `elapsed`, `response`, `timed_out` (exit 3 only).
   - `host.run(*args)`.
   - The `host_at(address)` and `host_unreachable` fixtures (F1-AC-22, F1-AC-23).
   - `simulator.exchange_log()` (F1-AC-12, F1-AC-20).
   - The timeout rule: the fixture never sets `--timeout`. `SHORT_TIMEOUT = "0.3"` is used only to save time in silent-device tests (F1-AC-15, F1-AC-16). F1-AC-21 passes `--timeout 0.3` because the AC states that value.
   - The simulator runs on a thread, and `host` wraps the real CLI (D6).
2.3 Write `validation.md`:
   - How each AC is verified: arrange through `control`, act through `host`, observe stdout, exit code, `GET_STATE` and, where the AC says so, the exchange log.
   - The timing rule for F1-AC-21, with fixed lower and upper bounds that take subprocess start-up into account.
   - The list of negative, edge and fault-injection scenarios.
   - The Traceability table, with one row per AC and the Test(s) cells empty for now.

**Done when:** `validation.md` has a row for every AC, and the traceability checker reports only "AC has no test" errors.

---

## 3. Simulator core: clock, relay state, line protocol

3.1 `clock.py`: a `Clock` protocol with `now() -> float`, and a `ManualClock` (starts at `0.0`, `advance(sec)`, `reset()`). The simulator never reads wall time. No F1 rule depends on time, but Phase 2's BUSY rule will.
3.2 `relay.py`: a `RelayDevice` with:
   - State `OFF`/`ON` (initial `OFF`), `fault` and `silent` flags, a `clock`, and a lock.
   - `handle_line(raw: bytes) -> bytes | None`, where `None` means no response.
   - `set_state`, `set_fault`, `set_silent`, `get_state`, `reset` and `advance_time`, used by the control API.
3.3 `protocol.py`: a `LineReader` that turns a byte stream into lines:
   - It splits on `\n` and strips **one** trailing `\r` (req §2.1).
   - It switches to discard mode as soon as the buffered bytes can no longer form a line of 32 bytes or fewer. That means more than 33 bytes, or 33 bytes whose last byte isn't `\r`. This way a 32-byte line followed by `\r\n` is still accepted (req §2.4).
   - In discard mode it drops bytes up to the next `\n`, then yields one *too-long* marker. Memory stays bounded however long the line is.
   - A partial line left when the connection closes is dropped without a response (req §7).
3.4 Classify each line in `handle_line` in the req §2.5 order: silent → fault → too long → empty → unknown → valid command.
   - "Unknown" means anything other than exactly `ON`, `OFF` or `STATUS`, including bytes above `0x7F`.
   - Errors never change state. A repeated `ON`/`OFF` returns `OK` with no change.
3.5 Responses are exactly one ASCII line ending in `\n`: `OK`, `STATUS ON`, `STATUS OFF`, `ERR UNKNOWN_CMD`, `ERR EMPTY`, `ERR TOO_LONG`, `ERR FAULT`.

**Done when:** `tests/unit/test_relay_device.py` and `tests/unit/test_line_reader.py` pass. Together they cover every req §2.5 precedence row, every req §3 error, the 32 / 32 + `\r` / 33 / 10 000-byte boundaries, and a line split across several reads.

---

## 4. Simulator serial server and exchange log

4.1 `server.py`: a `socketserver.TCPServer` on the serial port. For each connection: read bytes → `LineReader` → `RelayDevice.handle_line` → write the response, if there is one. Only the standard library is used.
4.2 `exchange_log.py`: a thread-safe in-memory log of `(timestamp, direction, bytes)` entries, with `entries()` and `clear()`. Timestamps are wall-clock and used only for the report. They never drive behaviour.
4.3 `simulator.py`: a `Simulator` facade.
   - It starts and stops the serial and control servers on background threads.
   - It exposes the bound ports (`serial_port`, `control_port`).
   - It owns one `RelayDevice` and one `ExchangeLog`.
4.4 `relay_sim/__main__.py`: the `relay-sim` entry point with the D2 options. It runs until Ctrl+C.

**Done when:** `tests/unit/test_server.py` passes. It starts a `Simulator` on port `0` and uses a raw socket to check:
   - Each response from req §2.2 and §3.
   - A 10 000-byte line gets exactly one `ERR TOO_LONG`, and the next command on the same connection is answered.
   - The exchange log records RX and TX entries.

---

## 5. Control API

5.1 `control.py`: a TCP server on the control port that implements the §0.1 wire format by calling the `RelayDevice` methods. It never goes through the serial protocol.
5.2 `RESET` restores the initial condition (req §2.3, §5) and clears the exchange log, so each test's report shows only its own exchange.
5.3 A small `ControlClient` in `tests/e2e/helpers.py` (only tests use it), with `set_state`, `get_state`, `fault`, `silence`, `reset` and `advance_time`. It raises an error on any `ERR` response.

**Done when:** `tests/unit/test_control.py` passes. It uses `ControlClient` against a `Simulator` and checks every command in §0.1, including an `ERR` for an unknown command.

---

## 6. Host client library and CLI

6.1 `client.py`: `RelayClient(address, timeout)` with `send_line(line: str) -> str`.
   - It validates the address (req §4.1).
   - It opens `serial.serial_for_url(f"socket://{address}", timeout=timeout)`.
   - It writes `line` encoded as UTF-8 plus `\n` (D5), reads one line, closes the connection, and returns the response without the `\n`.
   - It raises `HostConnectError` (→ exit 4) when the address is invalid or the connection can't be opened.
   - It raises `HostTimeout` (→ exit 3) when no full line arrives within `timeout`.
6.2 `cli.py` (argparse): takes the address from `RELAY_HOST_ADDRESS` or its default (D1), `--timeout` (finite float > 0, default `1.0`), and the subcommands `on`, `off`, `status` and `send <line>`.
   - Usage errors exit 2 before connecting: an unknown subcommand, missing or extra arguments, a `send` line containing `\n`, or an invalid `--timeout` (req §4.3).
6.3 Output (req §4.3):
   - When the device responds, write the response plus exactly one `\n` as bytes to `sys.stdout.buffer`, so Windows newline translation can't add `\r`.
   - Exit 1 if the response starts with `ERR `, otherwise 0.
   - For exits 2, 3 and 4, stdout stays empty and a short message goes to stderr.
6.4 `send` makes no changes to the line: no trimming, no case change, no length check, and empty input is allowed (req §4.2).
6.5 The host imports nothing from `relay_sim` and never connects to the control port.

**Done when:** `tests/unit/test_cli.py` passes. It runs the CLI as a subprocess and produces each exit code:
   - 0, 1 and 3 against a `Simulator`.
   - 2 for a usage error.
   - 4 for an unreachable or invalid address.

---

## 7. E2E test infrastructure (`tests/e2e/`)

Follows the `e2e-test-conventions` skill and the fixture contract from 2.2.

7.1 `helpers.py`: `wait_until(condition, timeout, interval=0.05, message=None)` (the only place a short sleep is allowed), `ControlClient` (5.3), `HostResult`, and `SHORT_TIMEOUT = "0.3"`.
7.2 `conftest.py`:
   - `simulator`: a session-scoped `Simulator` on ports `0`, plus a function-scoped `RESET` before each test, so every test starts clean and tests can run in any order. It exposes `exchange_log()`.
   - `control`: a `ControlClient` bound to the simulator's control port.
   - `host_at(address)`: a factory that runs `sys.executable -m relay_host ...` with `subprocess.run`.
     - `RELAY_HOST_ADDRESS=<address>` and `PYTHONPATH` (pointing at `src`) are set in the child process's environment only.
     - It returns a `HostResult` and adds no `--timeout`.
     - Members: `on()`, `off()`, `status()`, `send_raw(line)`, `run(*args)`.
   - `host`: `host_at("127.0.0.1:<serial_port>")`.
   - `host_unreachable`: `host_at` pointed at a port that was bound and then released, so nothing listens there.
7.3 A pytest-html hook (`pytest_runtest_makereport`) that, for every E2E test, passed or failed:
   - attaches the test's exchange log (simulator RX/TX with timestamps) and host runs (D8) to the report;
   - appends the same entries to `reports/exchange.log`.
   - The hook reads the log before the next test's `RESET` clears it.
7.4 `tests/unit/test_report_logging.py` uses pytest's `pytester` to run a tiny E2E test in a sub-session. It checks that the generated `report.html` and `exchange.log` both contain that test's RX `STATUS` and TX `STATUS OFF` entries with timestamps, and its host run. This makes the logging requirement an automated check, not a manual look at the report.

**Done when:** 7.4 passes, and a first E2E test (F1-AC-01) passes through these fixtures with its exchange in both `reports/report.html` and `reports/exchange.log`.

---

## 8. E2E tests for F1 ACs

The tests are derived only from req §6 and `validation.md`, never from the implementation code.
- Each test is named `test_F1_AC_NN_<description>`, and its docstring starts with the AC ID.
- There's no `sleep`, `skip` or `xfail`.

| Group | File | ACs | Kind |
|---|---|---|---|
| 8.1 Relay control | `test_f1_relay_control.py` | F1-AC-01 … F1-AC-07 | positive, edge (repeated ON/OFF, trailing CR) |
| 8.2 Input errors | `test_f1_input_errors.py` | F1-AC-08 … F1-AC-12 | negative, edge (lowercase, whitespace, unknown, non-ASCII, empty, 32 / 32 + CR / 33 / 10 000 bytes) |
| 8.3 Fault, silence, reset | `test_f1_fault_silence_reset.py` | F1-AC-13 … F1-AC-17 | fault injection (fault, silent device, silent + faulted, no replay, reset) |
| 8.4 Host CLI | `test_f1_host_cli.py` | F1-AC-18 … F1-AC-23 | negative (usage errors, invalid address), timeout, connection failure |

8.5 Every test that checks "the state doesn't change" also reads `control.get_state()`, not only the host output.
8.6 Each input listed in an AC is a separate parametrized case.
8.7 Fill in the Test(s) column of the traceability table in `validation.md` in the same change that adds the tests.

**Done when:** every AC has at least one test, and the traceability checker passes with no errors.

---

## 9. Validation run and Phase 1 close-out

9.1 Run `python .claude/skills/e2e-test-conventions/scripts/check_traceability.py` and get exit code 0.
9.2 Run `pytest` from the repo root and get a fully green suite, including 7.4. Confirm that `reports/exchange.log` has a section for every E2E test node ID.
9.3 Confirm the tests are independent:
   - Run each E2E test file on its own.
   - Run one test from each file on its own (`pytest path::test_F1_AC_NN_...`).
9.4 If a test fails, follow the skill's §6: fix the implementation, or raise a spec question. Never weaken a test.
9.5 Record the results in `validation-results.md` §2 (linked from `validation.md` Results): date, commit, pass count, independence runs and any open spec questions.
9.6 Add a `CHANGELOG.md` entry for F1 (what the feature delivers, its ACs, and the validation result). Every phase gets an entry (roadmap). Confirm README.md is current.
9.7 Ask the user to sign off. Only after sign-off, mark Phase 1 done in `specs/roadmap.md`. *Done 2026-11-19: signed off by the user, roadmap updated.*

**Done when:** all Phase 1 completion criteria in `specs/roadmap.md` are met and the user has signed off.

---

## 10. Forward compatibility with Phase 2 (no F1 work)

- `ManualClock` and `ADVANCE_TIME` already exist, so Phase 2's BUSY window can be measured on simulated time.
- `RelayDevice.handle_line` keeps the place where a valid command changes state separate from the place where it doesn't. A repeated `ON` is not a toggle (req §9), so this is where the rate-limit check will go.
- No `ERR BUSY` is implemented or tested in F1.

## 11. Open questions

None.

---

## 12. Change C1: interactive shell (`relay-host shell`)

Implements req §4.4 and F1-AC-24 … F1-AC-29. Groups 1–9 were done first. The Phase 1 sign-off (9.7) followed after this group. Same order as before: documents, then code, then tests, then validation.

### Decisions for C1

| ID | Decision |
|---|---|
| D9 | **Input is read as bytes.** The shell reads `sys.stdin.buffer` line by line and strips `\r\n` or `\n`. The remaining bytes go to the device unchanged, so piped input and the Windows console (which delivers UTF-8) behave the same. A UTF-8 byte-order mark at the very start of the input is dropped once (req §4.4, F1-AC-29; added 2026-11-19). |
| D10 | **Shared send path.** `RelayClient` gets `send_bytes(data: bytes) -> str`. `send_line` becomes `send_bytes(line.encode("utf-8"))`. Single runs and the shell then use the same connect / send / read / close code and the same `HostConnectError` / `HostTimeout` errors. |
| D11 | **Prompt.** `relay> ` is written to stdout, without a newline, only when `sys.stdin.isatty()` is true (req §4.4). |
| D12 | **Test interface.** The `host` fixture gets two members: `host.shell(input, *args)` for a whole session, and `host.open_shell(*args)` for a session that stays open while the test does something else (F1-AC-26). See 12.2. |

### Tasks

12.1 Review requirements change C1. *Done 2026-11-19.*

12.2 Update the fixture contract (`.claude/skills/e2e-test-conventions/references/fixtures-and-control-api.md` → v1.3) before any fixture code. *Done 2026-11-19.*
   - `host.shell(input: str, *args: str) -> HostResult` runs `relay-host [*args] shell`. It writes `input` (UTF-8) to stdin, closes stdin and waits for the exit.
   - `host.open_shell(*args: str) -> ShellSession` starts the shell and returns at once, with stdin left open. `ShellSession.write(text)` writes more input and keeps stdin open. `ShellSession.finish(input: str = "") -> HostResult` writes `input`, closes stdin and waits for the exit.
   - Both are logged like other host runs (D8), and the log also shows the stdin text.
   - `host_at(...)` and `host_unreachable` get the same two members.

12.3 Update `validation.md`. *Done 2026-11-19.*
   - Verification steps for F1-AC-24 … F1-AC-28.
   - The shell rows in the scenario-coverage table.
   - Prompt and Ctrl+C listed as checked by hand (req §7).
   - Traceability rows for the new ACs, with empty Test(s) cells.
   - F1-AC-25 uses the default 1.0 s timeout (the user chose not to extend `SHORT_TIMEOUT` to it, 2026-11-19). That adds about 2 s against the silent device, plus about 4 s for the no-simulator case on Windows (2 s per refused connection).

12.4 Host implementation (`src/relay_host/`). *Done 2026-11-19.*
   - `client.py`: `send_bytes` (D10). `send_line` delegates to it.
   - `cli.py`: a `shell` subparser with no arguments, so an extra argument → argparse exit 2. The shell loop:
     - For each line read (D9): strip the line ending, call `send_bytes`, then print the response plus `\n` as bytes to stdout (as in 6.3). On `HostTimeout` or `HostConnectError`, write one line to stderr and continue.
     - Show the prompt only when stdin is a terminal (D11).
     - End of input → exit 0. `KeyboardInterrupt` → exit 0, with no traceback.
   - `send`, `on`, `off` and `status` stay unchanged.

**Done when:** `tests/unit/test_cli_shell.py` passes. It runs the shell as a subprocess with piped input and checks:
   - the responses in order,
   - a line split as `\r\n`,
   - a stderr line per failed input line,
   - exit 0 on end of input,
   - exit 2 for an extra argument,
   - no prompt when piped.

All earlier tests must still pass.

12.5 E2E fixtures: implement `host.shell` and `host.open_shell` in `tests/e2e/conftest.py` as in 12.2. *Done 2026-11-19.*

12.6 E2E tests in `tests/e2e/test_f1_host_shell.py` for F1-AC-24 … F1-AC-28 (F1-AC-29 was added in 12.8a). *Done 2026-11-19.* They are derived only from req §6 and `validation.md`, and are named and documented as in §8. Fill in their traceability rows in the same change.

**Done when:** the traceability checker reports every AC covered and 0 errors (28/28 after 12.6, 29/29 after 12.8a).

12.7 Check by hand in a real PowerShell window (not automatable, req §7). *Done 2026-11-19 by the user: all as expected (validation-results.md §3).*
   - the `relay> ` prompt appears,
   - `ON` → `OK`,
   - Ctrl+Z then Enter exits 0,
   - Ctrl+C exits 0 with no traceback.

Record the result in `validation-results.md`.

12.8 Documentation: add a "Shell" section to `README.md`. *Done 2026-11-19.* Update the Phase 1 `CHANGELOG.md` entry to include the shell. Run every README example before publishing it.

12.8a *Done 2026-11-19.* Byte-order mark (found in 12.8 when the PowerShell pipe example failed; approved by the user 2026-11-19). Spec first: req §4.4, F1-AC-29, the validation.md steps and traceability row. Then drop the mark in `run_shell`, add a unit test and the E2E test for F1-AC-29, and re-run the README example.

12.9 Re-run the step 9 checks. *Done 2026-11-19 (validation-results.md §4); the shell mutation check was skipped by the user's decision.*
   - the checker,
   - the full `pytest` run,
   - each E2E file on its own, and one test per file on its own,
   - a mutation check of the shell (at least 4 mutations).

Record the results in `validation-results.md` as a new section. Then return to 9.7, the Phase 1 sign-off.

**Done when:** all of 12.1–12.9 are complete, and the Phase 1 criteria hold for F1-AC-01 … F1-AC-29.
