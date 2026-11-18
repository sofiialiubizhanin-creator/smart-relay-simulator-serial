---
name: e2e-test-conventions
description: The contract for the Smart Relay Simulator's end-to-end tests in tests/e2e/. It covers deriving tests from specs/<date>-<feature>/requirements.md and validation.md, the simulator/host/control fixtures, AC-ID naming and traceability, waiting without sleep, and when a test may change. Use it whenever you write, add, change, review, debug or fix a test under tests/e2e/. This includes covering an Acceptance Criterion (e.g. "add a test for F1-AC-03"), adding negative, edge or fault-injection cases, updating tests after a requirements.md change (such as the BUSY rate-limit change request), and investigating a red E2E suite, even when the user never says "conventions". Do not use it to implement simulator, host or transport code, for unit tests outside tests/e2e/, for editing requirements/plan/validation documents when no test changes, or for general Python or pytest questions unrelated to this project's E2E suite.
---

# E2E test conventions (v1)

In this project the E2E suite is the contract. A feature is done when every Acceptance Criterion (AC) is covered by a green E2E test (`specs/roadmap.md`). A test is only useful if it states what the requirements say, traces back to them, and is trustworthy. A test bent until it passes is worse than a red one, because it hides a real disagreement between spec and code. Every rule below follows from that.

Files in `specs/` take precedence over this skill and over your own assumptions. If they conflict, stop and ask.

## 1. Start from the spec, never from the code

Before writing or changing a test, read:
- `specs/<date>-<feature>/requirements.md`: the ACs and the protocol (command strings, response format, error codes, timeouts).
- `specs/<date>-<feature>/validation.md`: how each AC is verified, and the traceability table.

Don't open simulator, host or transport source to decide what a test should expect. Expectations copied from the implementation carry its bugs into the contract. You may read `tests/e2e/conftest.py` and the test helpers so you use the fixtures correctly.

**Don't invent protocol details.** Exact command strings, response text, error codes and the way the host reports a timeout all come from requirements.md. Copy them literally. If a requirement doesn't state the expected observable result, the spec has a gap. Stop and raise a spec question instead of guessing, because a guessed string becomes a contract nobody agreed to.

## 2. Fixtures (`tests/e2e/conftest.py`)

| Fixture | What it is | Use it for |
|---|---|---|
| `simulator` | A fresh or reset simulator for each test | Isolation: tests share no state and pass in any order |
| `host` | The host utility the test drives | **Every** relay command, including raw malformed lines for negative cases |
| `control` | The simulator control API | Setup, fault injection, observation, and advancing simulated time. **Never** relay commands |

Data flow: test → `host` → serial-over-TCP → simulator. `control` sets up the stage and observes it but never acts as the device's client. A test that sends `ON` through `control` checks nothing about the real path.

The fixtures hide whether the simulator is a thread or a subprocess, and whether `host` wraps the CLI or the client library. Use only the documented interface. The full method contract, return values and `wait_until` are in **[references/fixtures-and-control-api.md](references/fixtures-and-control-api.md)**. Read it before your first use of `host`, `control` or `wait_until` in a session.

## 3. Naming and traceability

```
test_<FeatureID>_AC_<NN>_<short_description>
```

```python
def test_F1_AC_03_lowercase_command_rejected(host, control):
    """F1-AC-03: <AC title, copied from requirements.md>."""
    control.set_state(...)                   # arrange via control (values from requirements.md)
    result = host.send_raw("on")             # act only through host
    assert result.response == EXPECTED       # exact expected text from requirements.md
    assert control.get_state() == ...        # optional independent observation
```

- The docstring's first line starts with the AC ID in hyphen form (`F1-AC-03`), matching the name.
- One test verifies one AC. Several tests per AC are fine. If a scenario seems to need two ACs, write two tests.
- Put each feature's tests in `tests/e2e/test_<featureid>_<topic>.py`, e.g. `test_f1_relay_control.py`.
- Every feature needs **positive, negative, edge and fault-injection** tests. Examples are unknown command, lowercase, empty line, repeated `ON`, and silent device. If an important negative case has no AC, propose a new AC to the user. Don't write an untraceable test.

The traceability table format and the checker are described in **[references/traceability.md](references/traceability.md)**.

## 4. Waiting and time

- **No `time.sleep` in tests.** Sleeps are slow when generous and flaky when tight, and they hide what the test is waiting for.
- For a real asynchronous event, such as a response arriving or a connection closing, use `wait_until(condition, timeout)`.
- For a rule based on time, such as a rate limit or a simulator-side timeout, use `control.advance_time(seconds)`. The simulator runs on an injectable clock, so never let real time pass to test simulated time.

## 5. Logging

The fixtures automatically capture the timestamped host↔simulator exchange log into the pytest-html report in `reports/`. Don't add `print`, `logging` or your own capture in tests, because it duplicates the report. Put context in assertion messages instead.

## 6. When a test may change

Never change, delete, skip, `xfail` or weaken a test to make it pass unless requirements.md changed first. Loosening an assertion and raising a timeout both count as weakening.

When an E2E test fails:
1. Re-read the AC in requirements.md.
2. If the test matches the requirement, the implementation is wrong. Report it. Fixing implementation code is outside this skill.
3. If the test contradicts the requirement (a wrong string copied, a fixture misused), fix the test without changing its AC or intent, and say what you fixed.
4. If the requirement is ambiguous or contradicts itself, stop and ask the user a spec question. Don't decide alone.

After a requirements change (e.g. Phase 2's BUSY rate limit):
- Check that requirements.md already describes the change in its "Changes" section. If it doesn't, stop, because the spec comes first.
- Add tests for new ACs and update tests for changed ACs. In each changed test's docstring, add a line that names the change (see references/traceability.md).
- Delete a test only when requirements.md removed its AC.
- Run the whole suite. Earlier features must stay green.

## 7. Finish (and review checklist)

1. Update the traceability table in the feature's `validation.md`.
2. Run `python .claude/skills/e2e-test-conventions/scripts/check_traceability.py` from the repo root and fix every ERROR.
3. Run `pytest` from the repo root. One command runs everything, so don't introduce tests that need extra steps.
4. Report which ACs are covered, which tests were added or changed, and any open spec questions.

When reviewing E2E tests, check the same points: derived from the spec, correct name and docstring, `host` and `control` used correctly, no sleep, no custom logging, nothing weakened, validation.md updated, checker clean.
