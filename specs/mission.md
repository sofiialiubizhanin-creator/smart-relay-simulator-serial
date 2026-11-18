# Mission

# What we build

A Smart Relay Simulator: a software model of a single relay that is controlled through a text command protocol over serial-over-TCP. It comes with a host utility which have CLI for controlling the relay from a terminal. No real hardware is used.

# For whom we build

- Developers and test engineers who need to verify relay-control logic without hardware.
- An AI coding agent that implements and tests features using Spec-Driven Development, with a human setting requirements, reviewing and validating.

# Quality Principles

1. **Traceability.** - every Acceptance Criterion has a unique ID (e. g. `F1-AC-01`) and is covered by at least one E2E test. Each test references its AC ID.
2. **Requirements-first testing.** - E2E tests are derived from `requirements.md` and `validation.md`, never frim implementation code.
3. **Negative coverage.** - every feature includes negative and edge scenarios, including fault injection through the simulator control API.
4. **Spec before behavior.** - any behavior change starts with an update to `requirements.md`.
5. **Tests are the contract.** - the agent must not change, delete, skip or weaken a test to make it pass unless the requirements changed first. If a test fails, raise a spec question.
6. **Precedence.** - the files in `specs/` override agent assumptions. If they conflict, the agent stops and asks.