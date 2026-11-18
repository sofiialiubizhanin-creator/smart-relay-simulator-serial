# Tech Stack

## Stack
- **Language:** Python 3.11+
- **Transport:** serial-over-TCP. The host uses pyserial with `serial_for_url("socket://host:port")`.
- **Simulator:** Python standard library only (`socket`/`socketserver`, `threading`).
- **Testing:** pytest and pytest-html. The HTML report includes the exchange log.

## Architecture

- **Simulator:** a TCP server that models one relay as a state machine (`OFF`/`ON` plus fault states). It has an injectable clock, so tests never depend on wall time.
- **Control API:** a separate TCP port used only by tests. It can set state, inject a fault, make the device silent, reset, and advance the clock. It is never used by the host.
- **Host:** a CLI utility (`relay-host on|off|status`) built on a small client library. It talks to the simulator only through the serial protocol.
- **Data flow:** test → host → (serial-over-TCP) → simulator. The test uses the control API only to set up conditions, inject faults and observe state, never to send relay commands.

## Testing conventions

- **No sleep:** waiting is done by pulling with a timeout (`wait_until(condition, timeout)`), and simulator time move only through the controlled API.
- **Independent Tests:** each test gets a fresh or reset simulator through fixtures, so tests share no state and can run in any order.
- **One command:** `pytest` run the full suite and produces the report.
- **Traceability:** test names and docstrings reference AC IDs (e.g. `test_F1_AC_01_...`).
- **Logging:** every exchange between host and simulator is logged with timestamps into the test report.
- **Skill:** the agent must use the test-conventions skill whenever it writes or changes E2E tests.