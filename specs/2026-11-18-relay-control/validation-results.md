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

## 2. Validation run (2026-11-19)

**Commit:** `e8f7acb`. **Environment:** Windows 11, Python 3.14.10, pytest 9.2.0, pytest-html 4.2.0, pyserial 3.5.

| Plan task | Check | Result |
|---|---|---|
| 9.1 | `check_traceability.py` | 23/23 ACs covered, 25 test functions, 0 errors, 0 warnings (exit 0) |
| 9.2 | `pytest` (one command, full suite) | **262 passed** in 58.4 s: 59 E2E cases + 203 component tests (exit 0) |
| 9.2 | `reports/exchange.log` | A section for every one of the 59 E2E cases, each marked passed |
| 9.3 | Each E2E file on its own | `test_f1_relay_control.py` 7 passed · `test_f1_input_errors.py` 19 passed · `test_f1_fault_silence_reset.py` 11 passed · `test_f1_host_cli.py` 22 passed |
| 9.3 | One test per file on its own | F1-AC-07, F1-AC-12 (10 000 bytes), F1-AC-16, F1-AC-22: each passed |

**F1-AC-21 timing margins** (validation.md §2; 5 extra runs during step 8): default timeout 1.45–1.48 s, `--timeout 0.3` 0.75–0.78 s, difference 0.69–0.72 s against the allowed 0.5–0.9 s.

**Roadmap Phase 1 required cases:** unknown command (F1-AC-10), lowercase (F1-AC-08), empty line (F1-AC-11), repeated `ON` (F1-AC-05), silent device (F1-AC-15). All are covered and passing.

**Open spec questions:** none.

**Not verified end to end** (as stated in validation.md §4): bounded memory for very long lines (covered by a component test), a connection closed before `\n`, and the wording of stderr messages.

§2 covers F1-AC-01 … F1-AC-23, as they were before change C1. The run including C1 is in §4.

## 3. Shell hand check, change C1 (2026-11-19)

**Purpose:** check the shell behaviour that needs a real terminal and can't be automated (req §4.4 and §7; plan 12.7).
**Done by:** the user, in Windows PowerShell, with `relay-sim` running in a second window. **Code:** the working tree after plan 12.6, on top of commit `e8f7acb` (later committed as `b90c25c`).

| # | Step | Expected | Result |
|---|---|---|---|
| 1 | `relay-host shell` | Prompt `relay> ` appears | As expected |
| 2 | `ON` | `OK` and a new prompt | As expected |
| 3 | `STATUS` | `STATUS ON` | As expected |
| 4 | `on` | `ERR UNKNOWN_CMD` | As expected |
| 5 | Empty line | `ERR EMPTY` | As expected |
| 6 | Ctrl+Z, Enter | The shell ends | As expected |
| 7 | `$LASTEXITCODE` | `0` | As expected |
| 8 | New shell, then Ctrl+C | The shell ends with no error trace | As expected |
| 9 | `$LASTEXITCODE` | `0` | As expected |

**Result:** all steps as expected. The prompt, end of input and Ctrl+C behave as req §4.4 specifies.

## 4. Validation run including change C1 (2026-11-19)

**Code:** the working tree after plan 12.8a (C1 with the byte-order-mark amendment), on top of commit `e8f7acb` (later committed as `b90c25c`). **Environment:** as in §2.

| Plan task | Check | Result |
|---|---|---|
| 12.9 / 9.1 | `check_traceability.py` | 29/29 ACs covered, 32 test functions, 0 errors, 0 warnings (exit 0) |
| 12.9 / 9.2 | `pytest` (one command, full suite) | **286 passed** in 74.0 s: 66 E2E cases + 220 component tests (exit 0) |
| 12.9 / 9.2 | `reports/exchange.log` | A section for every one of the 66 E2E cases, each marked passed |
| 12.9 / 9.3 | Each E2E file on its own | `test_f1_relay_control.py` 7 passed · `test_f1_input_errors.py` 19 passed · `test_f1_fault_silence_reset.py` 11 passed · `test_f1_host_cli.py` 22 passed · `test_f1_host_shell.py` 7 passed |
| 12.9 / 9.3 | One test per file on its own | F1-AC-07, F1-AC-12 (10 000 bytes), F1-AC-16, F1-AC-22, F1-AC-26: each passed |
| 12.7 | Shell hand check | All as expected (§3) |
| 12.8a | README PowerShell pipe example, extended with `on` (`"ON", "STATUS", "on" \| relay-host shell`) | `OK`, `STATUS ON`, `ERR UNKNOWN_CMD`, exit 0 |

**Mutation check of the shell: skipped**, by the user's decision on 2026-11-19 (it would take about 5 minutes). The §1 mutation check (15/15) covers F1-AC-01 … F1-AC-23 only. So it is **not shown** that F1-AC-24 … F1-AC-29 fail for a faulty shell. For example, it isn't shown that F1-AC-26 catches a shell that holds its connection open.

**Open spec questions:** none.
