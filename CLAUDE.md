# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Spec-Driven Development project for a Smart Relay Simulator (one simulated relay controlled over serial-over-TCP, plus a host CLI). No hardware is involved. Phase 1 (F1, relay control and status, including `relay-host shell`) is implemented, validated and signed off (2026-11-19). Phase 2 (BUSY rate limit) is next.

`specs/mission.md`, `specs/roadmap.md` and `specs/tech-stack.md` are authoritative and override your own assumptions. If something conflicts with them, stop and ask instead of choosing yourself. Read them before starting any phase.

## Workflow

Each feature lives in `specs/<date>-<feature>/` and follows this cycle:
requirements.md → plan.md → validation.md → implementation → validation results. A phase is done only when its completion criteria in `specs/roadmap.md` are met, and the main criterion is a green E2E suite.

- Any behavior change starts with an update to `requirements.md`, never with code.
- Every Acceptance Criterion has a unique ID (e.g. `F1-AC-01`) and is covered by at least one E2E test that references that ID.
- Derive E2E tests from `requirements.md` and `validation.md`, never from implementation code.
- Tests are the contract. Do not change, delete, skip or weaken a test to make it pass unless the requirements changed first. If a test fails and the spec seems wrong, raise a spec question.
- Every feature needs negative, edge and fault-injection scenarios.
- Use the `e2e-test-conventions` skill (`.claude/skills/e2e-test-conventions/`) whenever you write, change, review or fix E2E tests in `tests/e2e/`. It defines the fixture contract (`simulator`, `host`, `control`), naming, and the validation.md traceability table.

## Commands

- `pytest` runs the full test suite (E2E and component tests) and produces the pytest-html report. Everything must stay runnable with this one command.
- `pytest path/to/test_file.py::test_F1_AC_01_name` runs a single test.
- `relay-host on|off|status|send <line>|shell` is the host CLI.
- `python .claude/skills/e2e-test-conventions/scripts/check_traceability.py` checks AC ↔ test ↔ validation.md traceability (exit 1 on errors).

## Architecture

Python 3.11+.

- **Simulator** (standard library only: `socket`/`socketserver`, `threading`): a TCP server that models one relay as a state machine (`OFF`/`ON` plus fault states). It uses an injectable clock, so nothing depends on wall time.
- **Control API**: a separate TCP port on the simulator that only tests use. It can set state, inject faults, make the device silent, reset, and advance the clock. The host must never use it.
- **Host**: a small client library plus the `relay-host` CLI. It talks to the simulator only through the text serial protocol, via pyserial `serial_for_url("socket://host:port")`.
- **Data flow**: test → host → (serial-over-TCP) → simulator. Tests use the control API only to set up conditions, inject faults and observe state, never to send relay commands.

## Testing conventions

- No `sleep`. Wait by polling with a timeout (`wait_until(condition, timeout)`), and move simulator time only through the control API.
- Each test gets a fresh or reset simulator through fixtures. Tests share no state and must pass in any order.
- Test names and docstrings reference AC IDs, e.g. `test_F1_AC_01_...`.
- Every host↔simulator exchange is logged with timestamps into the HTML report.

## Roadmap snapshot

- **Every phase** ends with a `CHANGELOG.md` entry and a `README.md` that explains how to run the program and all tests with one command.
- **Phase 1 (done, signed off 2026-11-19):** simulator, control API, host CLI (including `relay-host shell`), transport, and the commands `ON` / `OFF` / `STATUS` with error handling. Negative cases include unknown command, lowercase, empty line, repeated `ON`, and a silent device.
- **Phase 2 (in progress):** reject a toggle that comes within 2 seconds of the previous one with `BUSY`, tested with the controlled clock. This phase also requires a "Changes" section in the F1 `requirements.md` and traceability for any updated F1 tests.
