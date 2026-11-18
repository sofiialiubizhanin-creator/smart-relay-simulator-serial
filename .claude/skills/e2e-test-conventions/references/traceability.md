# Traceability: names, docstrings, validation.md table, checker

## AC IDs

The format is `<FeatureID>-AC-<NN>`, e.g. `F1-AC-03`. IDs are defined in `specs/<date>-<feature>/requirements.md`. Never create an AC ID that isn't defined there.

## Test name

```
test_<FeatureID>_AC_<NN>_<short_description>
```
- `<FeatureID>` and `<NN>` are exactly as in the AC ID, with hyphens replaced by underscores: `F1-AC-03` becomes `test_F1_AC_03_...`.
- `<short_description>` is lowercase snake_case describing the scenario, not the implementation: `lowercase_command_rejected`, not `parser_raises_valueerror`.
- Add a suffix when one AC has several tests: `test_F1_AC_05_silent_device_status_times_out`, `test_F1_AC_05_silent_device_on_times_out`.

## Docstring

```python
"""F1-AC-03: Lowercase command is rejected.

Changed: <short name of the change, as in requirements.md "Changes"> (<date>)
"""
```
- The first line starts with the AC ID in hyphen form, matching the test name, followed by the AC title copied from requirements.md.
- Add a `Changed:` line only when the test was changed because of a requirements change. That makes changed tests traceable to the change request, as Phase 2 requires. Keep earlier `Changed:` lines and add new ones below them.

## validation.md traceability table

Each feature's `validation.md` has exactly one section in this format:

```markdown
## Traceability

| AC ID    | Test(s)                                                              | Notes |
|----------|----------------------------------------------------------------------|-------|
| F1-AC-01 | tests/e2e/test_f1_relay_control.py::test_F1_AC_01_on_turns_relay_on  |       |
| F1-AC-03 | tests/e2e/test_f1_relay_control.py::test_F1_AC_03_lowercase_command_rejected |  |
| F1-AC-05 | tests/e2e/test_f1_relay_control.py::test_F1_AC_05_silent_device_status_times_out<br>tests/e2e/test_f1_relay_control.py::test_F1_AC_05_silent_device_on_times_out | fault injection |
```
- Each AC in requirements.md gets one row, in the same order.
- Tests are listed as pytest node IDs relative to the repo root with forward slashes, joined by `<br>` when there are several.
- An AC with no test yet stays in the table with an empty Test(s) cell. The checker reports it, which keeps missing coverage visible.
- The table is updated in the same change that adds, renames, moves or deletes a test.
- Notes are free text, such as the test type (negative, edge, fault injection) or a reference to a change.

## Checker script

```
python .claude/skills/e2e-test-conventions/scripts/check_traceability.py
python .claude/skills/e2e-test-conventions/scripts/check_traceability.py --feature specs/<date>-<feature>
```
It uses only the standard library, runs from the repo root (or pass `--root`), and exits with code 1 if there are errors.

It reports these as ERROR:
- An AC in requirements.md with no test.
- A test that references an AC not defined in any requirements.md.
- A test function in `tests/e2e/test_*.py` whose name doesn't follow the pattern.
- A docstring that's missing, or whose first line doesn't start with the AC ID from the test name.
- `time.sleep` (or any `sleep(...)` call) in a test module.
- `pytest.mark.skip`, `skipif`, `xfail`, `pytest.skip()`, `pytest.xfail()` or `importorskip` in a test module.
- An AC missing from validation.md's table, a table link to a test that doesn't exist, or a test not listed under its AC.

It reports a WARN when a feature folder has no validation.md yet.

It doesn't check whether a test actually verifies its AC. That needs a human (or Claude) to read the test against the requirement.
