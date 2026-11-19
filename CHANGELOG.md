# Changelog

All notable changes to this project are recorded here, one entry per completed phase (see [specs/roadmap.md](specs/roadmap.md)).

## [0.1.0] - 2026-11-19 - Phase 1: Simulator + F1 (Relay control and status)

Specs: [requirements](specs/2026-11-18-relay-control/requirements.md) · [plan](specs/2026-11-18-relay-control/plan.md) · [validation](specs/2026-11-18-relay-control/validation.md) · [results](specs/2026-11-18-relay-control/validation-results.md)

### Added
- **`relay-sim`**: a simulator of one relay (`OFF` / `ON`) speaking a line-based ASCII protocol over serial-over-TCP (default `127.0.0.1:5555`).
  - Commands `ON`, `OFF`, `STATUS`. Responses `OK`, `STATUS ON`, `STATUS OFF`.
  - Errors `ERR UNKNOWN_CMD`, `ERR EMPTY`, `ERR TOO_LONG` (lines over 32 bytes, with bounded memory) and `ERR FAULT`, in a fixed precedence order.
  - Prints a timestamped log of every exchange.
  - Python standard library only, with an injectable clock (no wall time).
- **Control API** for tests only (default port `5556`): `SET_STATE`, `FAULT`, `SILENCE`, `RESET`, `ADVANCE_TIME`, `GET_STATE`.
- **`relay-host`**: a CLI with `on`, `off`, `status` and `send "<raw line>"` (sent unchanged), plus `--timeout` (default 1.0 s).
  - The address comes from `RELAY_HOST_ADDRESS` (default `127.0.0.1:5555`).
  - Exit codes: 0 OK, 1 device error, 2 usage error, 3 no response, 4 cannot connect or invalid address.
  - Built on pyserial `serial_for_url("socket://…")`.
- **`relay-host shell`** (requirements change C1): an interactive shell where you type protocol lines (`ON`, `OFF`, `STATUS`) and see each response.
  - Each line is sent exactly as typed, over a new connection per line, so an idle shell never blocks other clients.
  - It reports a missing response or connection problem on stderr and keeps going.
  - It shows the `relay> ` prompt only in a terminal. End of input or Ctrl+C exits with code 0.
  - It ignores the byte-order mark Windows PowerShell 5.1 adds when piping input.
- **E2E suite**: 66 cases covering all 29 acceptance criteria (F1-AC-01 … F1-AC-29), including negative, edge and fault-injection cases.
  - Every test's host ↔ simulator exchange is logged with timestamps into `reports/report.html` and `reports/exchange.log`.
  - Component tests for each part, plus an automated check that the logging works.
- **README** with setup and how to run the program and all tests with one command (`pytest`).

### Validation
- `pytest`: 286 passed (66 E2E + 220 component). Traceability checker: 29/29 ACs covered, 0 errors.
- Mutation check before C1: 15 of 15 planted bugs were caught by the E2E suite.
- Shell hand check in a real terminal (prompt, end of input, Ctrl+C): all as expected.
- Each E2E file and single tests also pass on their own.
- A mutation check of the shell was not run (skipped by decision). Details are in validation-results.md §4.

### Not included
- `ERR BUSY` and the toggle rate limit (Phase 2).
- Several hosts at once, persistence across restarts, real serial settings.
- What the host does when the device closes the connection before responding (out of F1 scope).
