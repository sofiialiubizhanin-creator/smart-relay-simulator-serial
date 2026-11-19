# Smart Relay Simulator

A software model of a single relay, controlled through a text command protocol over serial-over-TCP, plus a host CLI (`relay-host`) to control it from a terminal. No hardware is involved.

- `relay-sim`: the simulated relay. Listens on `127.0.0.1:5555` (relay commands) and `127.0.0.1:5556` (control API, used only by tests).
- `relay-host`: sends one command to the relay and prints the response.

Specifications live in [`specs/`](specs/): [mission](specs/mission.md), [roadmap](specs/roadmap.md), [tech stack](specs/tech-stack.md), and one folder per feature (requirements, plan, validation).

## Setup (once)

Requires Python 3.11 or newer. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -e .[test]
```

Activate the environment in every new terminal before using the commands below.

## Run the tests (one command)

```powershell
pytest
```

This runs the whole suite (E2E tests for every acceptance criterion, plus component tests) and writes:

- `reports/report.html`: the test report. Open a test's row to see its timestamped host ↔ simulator exchange.
- `reports/exchange.log`: the same exchange log as plain text, one section per test.

Both are regenerated on every run. Useful variations:

```powershell
pytest tests/e2e                                                                  # only the E2E suite
pytest "tests/e2e/test_f1_relay_control.py::test_F1_AC_01_initial_state_is_off"   # one test
python .claude/skills/e2e-test-conventions/scripts/check_traceability.py          # AC <-> test traceability
```

## Run the program

**Terminal 1: start the simulator.** It prints every exchange as it happens (`-q` to silence it). Stop it with Ctrl+C.

```powershell
relay-sim
```

**Terminal 2: control the relay.**

```powershell
relay-host status              # STATUS OFF
relay-host on                  # OK
relay-host status              # STATUS ON
relay-host send "on"           # ERR UNKNOWN_CMD   (send passes a raw line unchanged)
relay-host --timeout 0.5 off   # OK
$LASTEXITCODE                  # exit code of the last command (bash: $?)
```

| Exit code | Meaning |
|---|---|
| 0 | The device responded without an error (`OK`, `STATUS ON`, `STATUS OFF`) |
| 1 | The device responded `ERR <CODE>` |
| 2 | Usage error (nothing was sent) |
| 3 | No response within the timeout (default 1.0 s) |
| 4 | Cannot connect, or `RELAY_HOST_ADDRESS` is invalid |

The host connects to `127.0.0.1:5555` by default. To use another address, set `RELAY_HOST_ADDRESS=HOST:PORT`.

**Interactive session (optional).** To type protocol lines yourself and see each response, connect with pyserial's terminal:

```powershell
python -m serial.tools.miniterm --eol LF --echo socket://127.0.0.1:5555
```

Type `ON`, `OFF` or `STATUS` and press Enter. Exit with Ctrl+]. The simulator serves one connection at a time, so close miniterm before using `relay-host`.

## Protocol in brief

One ASCII command per line, ending with `\n`. Commands are exactly `ON`, `OFF` and `STATUS` (uppercase, no arguments). Responses: `OK`, `STATUS ON`, `STATUS OFF`, or `ERR UNKNOWN_CMD` / `ERR EMPTY` / `ERR TOO_LONG` (over 32 bytes) / `ERR FAULT`. The full definition is in [specs/2026-11-18-relay-control/requirements.md](specs/2026-11-18-relay-control/requirements.md).

## Project layout

```
src/relay_sim/     simulator: protocol, relay state machine, serial and control servers
src/relay_host/    host client library and the relay-host CLI
tests/e2e/         E2E suite (one test per acceptance criterion, named test_F1_AC_NN_...)
tests/unit/        component tests
specs/             mission, roadmap, tech stack, and per-feature specs
```
