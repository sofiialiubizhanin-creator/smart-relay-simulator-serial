# Mission

# What we build

A Smart Relay Simulator: a software model of a single relay that is controlled through a text command protocol over serial-over-TCP. It comes with a host utility with a CLI for controlling the relay from a terminal. No real hardware is used.

# For whom we build

- Developers and test engineers who need to verify relay-control logic without hardware.
- An AI coding agent that implements and tests features using Spec-Driven Development, with a human setting requirements, reviewing and validating.

# Quality Principles

1. **Traceability.** Every Acceptance Criterion has a unique ID (e.g. `F1-AC-01`) and is covered by at least one E2E test. Each test references its AC ID.
2. **Requirements-first testing.** E2E tests are derived from `requirements.md` and `validation.md`, never from implementation code.
3. **Negative coverage.** Every feature includes negative and edge scenarios, including fault injection through the simulator control API.
4. **Spec before behavior.** Any behavior change starts with an update to `requirements.md`.
5. **Tests are the contract.** The agent must not change, delete, skip or weaken a test to make it pass unless the requirements changed first. If a test fails, raise a spec question.
6. **Precedence.** The files in `specs/` override agent assumptions. If they conflict, the agent stops and asks.