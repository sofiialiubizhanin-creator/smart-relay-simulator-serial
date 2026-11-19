# F1: Relay control and status - Validation results

Results of validating F1 against [validation.md](validation.md). Newest results go at the end of each section.

## 1. Mutation check (2026-11-19)

**Purpose:** show that the E2E suite can fail. A suite that is green on its first run might also be too weak to catch bugs.

**Method:**
- One mutation at a time: a realistic bug was planted in the simulator or host source, `pytest tests/e2e` was run, and the failing tests were recorded.
- The original file was then restored. Afterwards `git status` confirmed `src/` was unchanged.
- **Source:** commit `65cf480`. **E2E tests:** the step 8 suite (59 cases, 23/23 ACs), not yet committed at the time.

**Result: 15 of 15 mutations caught (no survivors).**

| # | Planted bug | File | Caught by |
|---|---|---|---|
| M01 | Lowercase `ON` accepted | `relay_sim/relay.py` | F1-AC-08, F1-AC-18 |
| M02 | Fault checked before silence | `relay_sim/relay.py` | F1-AC-15 (silent + faulted case) |
| M03 | Silent device still executes `ON` | `relay_sim/relay.py` | F1-AC-15, F1-AC-16 |
| M04 | Unknown command resets state to `OFF` | `relay_sim/relay.py` | F1-AC-08 |
| M05 | Clearing a fault resets the state | `relay_sim/relay.py` | F1-AC-14 |
| M06 | `RESET` keeps silence | `relay_sim/relay.py` | F1-AC-17, plus 16 other tests |
| M07 | Trailing `\r` not stripped | `relay_sim/protocol.py` | F1-AC-07, F1-AC-11 |
| M08 | A 32-byte line counted as too long | `relay_sim/protocol.py` | F1-AC-12 |
| M09 | A 33-byte line accepted | `relay_sim/protocol.py` | F1-AC-12, F1-AC-19 |
| M10 | `send` trims whitespace | `relay_host/cli.py` | F1-AC-09 |
| M11 | `ERR` responses exit 0 instead of 1 | `relay_host/cli.py` | 10 tests (F1-AC-08 … 13, 18, 19) |
| M12 | Default timeout 2.0 s instead of 1.0 s | `relay_host/client.py` | F1-AC-21 |
| M13 | Output ends with `\r\n` | `relay_host/cli.py` | 20 tests (every AC whose response is checked) |
| M14 | `send` line containing `\n` allowed | `relay_host/cli.py` | F1-AC-20 |
| M15 | Connection failure exits 3 instead of 4 | `relay_host/cli.py` | F1-AC-22, F1-AC-23 |

**Findings:**
- **M06 failed 17 tests.** With `RESET` not clearing silence, silence leaks from one test into the next. This confirms that the reset before each test is necessary and that a broken reset can't go unnoticed.
- **M04 was caught by one test only.** Most negative tests start from `OFF`, where a bug that sets the state to `OFF` changes nothing visible. F1-AC-08's `off`/`Off` cases start from `ON` (validation.md V4), and they caught it. This is the thinnest coverage of the 15 mutations, but it is adequate.
- No test was changed for or during this check.

## 2. Validation run

Not run yet. Filled in by plan task 9.5 with the date, commit, pass count, independence runs and any open spec questions.
