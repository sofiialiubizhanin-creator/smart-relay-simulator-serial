# Skill evaluations: `e2e-test-conventions`

**Date:** 2026-11-19 · **Skill:** `.claude/skills/e2e-test-conventions/` · **Before:** v1.1, the version that wrote the F1 tests · **After:** v1.2

E2E tests check whether the relay behaves correctly. These evaluations check whether the **skill** makes an agent behave correctly when it works on those tests.

The skill was evaluated before Phase 2's implementation (change C2, BUSY), refined from the results, and evaluated again with the same cases.

## 1. Method

- **Cases:** 5 test cases.
  - 4 use this project's own data (its specs, tests and the pending change C2).
  - 1 is a negative case, where the skill should *not* be applied.
  - The cases live in `.claude/skills/e2e-test-conventions/evals/<case>/` (`prompt.md`, `case.yaml`, one `graders/NN-*.md` file per check), in the layout `claude plugin eval` reads.
- **Runs:**
  - One independent agent per case and version. 10 runs in total, one run each.
  - Each run got the user prompt and the path of the skill version under test (snapshots: `skill-snapshot-before/`, `skill-snapshot-after/`).
  - The agent decided by itself whether the skill applied.
  - Runs were read-only on the repository and wrote the files they would have changed into their own output folder. `git status` confirmed that `src/` and `tests/` were untouched after every round.
- **Grading:**
  - Each run was graded against fixed, objectively checkable statements ("checks"), by reading its outputs: the files, `response.md` and `run_notes.md`.
  - Grades with evidence are stored per run in `grading.json`.
- **Workspace (untracked):** `reports/skill-evals-workspace/`, which holds both snapshots, every run's outputs, `grading.json`, `timing.json`, `benchmark.md` and the review pages. For a side-by-side view, open `iteration-2/review.html`, which shows each "after" output with its "before" output.

## 2. Cases and checks

| # | Case | What it tests | Checks |
|---|---|---|---|
| 1 | `writes-busy-window-test` | Write the missing E2E test for F1-AC-32 (a rejected toggle doesn't restart the BUSY window) | 7: `test_F1_AC_32_…` name; docstring starts with the AC ID; commands only via `host`; time only via `advance_time`, no sleep; exact `ERR BUSY`/1 then `OK`/0; state via `control.get_state`; traceability row filled |
| 2 | `refuses-to-weaken-timing-test` | "Just bump the F1-AC-21 upper bound to 3.5 s so CI goes green" | 4: the bound isn't changed; explains the bounds are contract (validation.md §2); proposes a spec-first path or asks; no skip/xfail |
| 3 | `updates-test-after-change-request` | Update the existing tests that change request C2 affects | 7: `ERR BUSY` case added to F1-AC-19; setup toggles via `host`, not `SET_STATE`; `Changed:` line names C2; existing cases kept; no unrelated test changed; **X1** lists *all* affected tests, component tests included, with reasons; **X2** states the regression-first rule (unchanged suite against the implementation, failures recorded, before updating tests) |
| 4 | `reviews-bad-e2e-test` | Review a teammate's test file with planted problems | 5: flags missing AC IDs; `time.sleep`; weak assertions instead of exact strings; acting through `control` instead of `host`; suggests the traceability checker or the validation.md row |
| 5 | `does-not-apply-to-implementation` *(negative)* | "Implement the BUSY check in `relay.py`" | 4: implements BUSY correctly in `relay.py`; writes no file under `tests/e2e/`; doesn't modify validation.md; reports that it did not apply the skill |

**How the check set changed (both versions are graded on the final set):**
- The first 25 checks were written before any run. The baseline passed all 25, so they could not show an improvement.
- Three extra checks were then added to target gaps seen in the baseline runs: X1, X2, and X3 ("run only the affected tests while working").
- **X3 was dropped.** It contradicts the skill's own finish step, which says to run the full suite with `pytest`, and the regression rule, which needs a full run. It would have penalised runs for following the skill.
- The final set has **27 checks**, applied the same way to both versions.

## 3. Results

| Case | Before (v1.1) | After (v1.2) | Time before → after | Tokens before → after |
|---|---|---|---|---|
| 1. Write F1-AC-32 test | 7/7 | 7/7 | 85 s → 83 s | 88k → 85k |
| 2. Refuse to weaken timing test | 4/4 | 4/4 | 59 s → 46 s | 62k → 55k |
| 3. Update tests after C2 | **5/7** | **7/7** | 176 s → 120 s | 73k → 115k |
| 4. Review bad test | 5/5 | 5/5 | 92 s → 70 s | 74k → 71k |
| 5. Negative: implementation | 4/4 | 4/4 | 251 s → 166 s | 58k → 58k |
| **Total** | **25/27 (93%)** | **27/27 (100%)** | avg 133 s → 97 s | avg 71k → 77k |

**What changed between the versions:**
- **Case 3, X1 (before: fail → after: pass).** The v1.1 run checked only the E2E files and concluded "no other test is affected". The v1.2 run read every test under `tests/` and listed the four component tests C2 breaks: `test_relay_device::test_on_off_status`, `test_server::test_several_commands_on_one_connection`, `test_cli::test_on_off_status` and `test_cli_shell::test_lines_are_sent_as_typed_and_responses_printed_in_order`. It also listed one test (`test_every_response_is_one_ascii_line`) that becomes outdated but still passes. A separate implementation run confirmed exactly those four failures.
- **Case 3, X2 (before: fail → after: pass).** v1.1 cited "V10" but treated it as a static read and ran the full suite with its own edit already in place. v1.2 said that BUSY isn't implemented yet, so the regression run is still pending, that the list is what the run must confirm, and where its results go (validation-results.md §5).
- **Unchanged and correct in both versions:**
  - Refusing to weaken the timing test. Both runs also spotted that 2.62 s could be the real bug "default timeout 2.0 s" (mutation M12).
  - Catching all four planted problems in the review.
  - Skipping the skill for implementation work, based on its description alone.

## 4. Changes to the skill (v1.1 → v1.2)

1. **Regression first after a requirements change** (§6), the user's rule:
   1. Check the "Changes" section.
   2. List every test the change can affect across the whole suite, `tests/unit/` included, with the reason.
   3. Once the change is implemented, run the suite unchanged and record each failure.
   4. Update only the tests the change explains, each with a `Changed:` line. Any other failure is an implementation bug.
   
   The skill also explains why: updating tests first hides real regressions among the intended updates.
2. **"Arranging a state vs. arranging a history"** (§2): `control.set_state` sets a state but doesn't replay commands. When an AC depends on what an earlier relay command caused, such as a rate-limit window, the arrange step sends that command through `host`.

The skill is still 95 lines. The description and the references are unchanged.

## 5. Limitations

- **One run per case and version.** Differences in time and tokens are single samples. Case 3 took longer and used more tokens after the change, because the run read every test file; the variance is high (before 133 ± 79 s, after 97 ± 47 s).
- **Most checks didn't discriminate.** 25 of the 27 checks passed with both versions. The measured gain comes from the two checks written to target the gaps seen in the baseline.
- **Grading was done by the agent that ran the evaluation,** by reading each run's outputs and recording evidence per check. It was not a blind comparison.
- **Triggering was simulated.** The skill path was given in the prompt and the run decided whether to use it. Automatic triggering from the description alone wasn't measured; the skill-creator's description optimizer could do that later.

## 6. How to rerun

- **Agent workflow:** the same 5 cases can be run again with the skill-creator workflow. The cases and checks are in `.claude/skills/e2e-test-conventions/evals/`.
- **CLI (Claude Code v2.1.269 or later):** from the skill folder, `claude plugin eval . --allow-tools Write,Edit,Bash --scaffold`. The `--scaffold` flag is needed because case 4 has an input file. These are real, billed model runs.
