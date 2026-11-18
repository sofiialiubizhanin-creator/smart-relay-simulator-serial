# Roadmap

Each phase follows the cycle: requirements.md -> plan.md -> implementation -> validation. A phase is done when its completion criteria are met. The main criterion is **green E2E**.

## Phase 1: Simulator + F1 (Relay control and status) - *In progress*

**Scope:** relay simulator with a control API, host CLI, serial-over-TCP transport and the commands `ON`, `OFF`, `STATUS` with error handling.

**Completion Criteria:**
- Every F1 acceptance criteria is covered by at least one E2E test that references its AC ID.
- The full E2E suite is green and runs with one command.
- Negative and fault-injection scenarios are included (unknown command, lowercase, empty line, repeated `ON`, silent device).

## Phase 2: Change request - Toggle rate limit (BUSY) - *Planned*

**Scope:** the relay rejects the toggle that comes within 2 seconds of the previous one, with a `BUSY` error. Tests use controlled simulator time.

**Completion Criteria:**
- F1 requirements.md is updated, including a "Changes" section.
- New and changed ACs are covered by E2E tests.
- Regression: the full suite is green. Any update F1 tests are traced to the requirement change.
- A CHANGELOG.md entry is added.
- The README.md describes how to run everything with one command.