# Fixtures, control API and helpers: the contract (v1.2)

> v1.1 (2026-11-19), aligned with F1 `requirements.md`: `control.inject_fault(fault)` replaced by `control.fault(enabled)`; `HostResult` gained `exit_code`, `stdout`, `stderr`, `elapsed`; added `host.run(*args)` and the `host_unreachable` fixture; the fixture never sets a timeout, and one `SHORT_TIMEOUT` (0.3 s) is allowed for silent-device tests only; simulator runs on a thread and `host` wraps the real CLI.
>
> v1.2 (2026-11-19): added the `host_at(address)` factory (for F1-AC-23) and `simulator.exchange_log()` (for ACs that say what the simulator receives or sends).

This file defines the interface that E2E tests may rely on. `tests/e2e/conftest.py` and `tests/e2e/helpers.py` don't exist yet. When they are implemented they must match this contract, and if a change is needed this file is updated first.

Values such as relay states, fault names, command strings and response text are **not** defined here. They come from the feature's `requirements.md`. Where this file says `<from requirements.md>`, copy the value from there.

## Contents
- `simulator`
- `host`
- `host_at` and `host_unreachable`
- `control`
- `wait_until`
- Time: simulated vs real
- Open points (decide when implementing)

---

## `simulator`

- Each test gets either a fresh simulator instance or a shared one reset to its initial state. Either way, no state leaks between tests, and tests pass in any order and in isolation (`pytest path::test_name`).
- It runs in-process on a background thread. That's an implementation detail, and tests must not depend on it.
- Tests normally don't use `simulator` directly. `host` and `control` depend on it. Request it explicitly only when a test needs something it exposes:
  - `simulator.exchange_log()` returns this test's entries as `(timestamp, direction, data)`, where `direction` is `"RX"` (received by the simulator) or `"TX"` (sent by it) and `data` is the line as bytes. Use it only for ACs that state what the simulator receives or sends (e.g. "the simulator receives nothing", "exactly one response"). It is read-only.
- The fixture also starts the exchange-log capture that ends up in the pytest-html report. Tests don't log anything themselves.

## `host`

The host utility, already connected to the simulator over serial-over-TCP. Every relay command goes through it.

| Member | Meaning |
|---|---|
| `host.on()` | Send the "relay on" command as defined in requirements.md |
| `host.off()` | Send the "relay off" command |
| `host.status()` | Send the status query |
| `host.send_raw(line: str)` | Send `line` exactly as given (plus the line terminator the protocol defines). Use it for negative and edge cases: unknown command, lowercase, empty line, extra whitespace |
| `host.run(*args: str)` | Run the host with arbitrary arguments, exactly as given, already pointed at the simulator. Use it for usage errors (unknown subcommand, missing or extra arguments, invalid options) and for options such as `--timeout`. Example: `host.run("--timeout", "0.3", "status")` |

Each call returns a `HostResult`:

| Field | Meaning |
|---|---|
| `exit_code: int` | The host's exit code. The meaning of each value is `<from requirements.md>` |
| `stdout: str` | Everything the host printed to stdout, unchanged. Use it to check "exactly the response line" or "nothing on stdout" |
| `stderr: str` | Everything the host printed to stderr. Requirements don't fix its text, so don't assert on exact wording |
| `elapsed: float` | Real seconds from starting the host to its exit. Use it only for ACs that state a duration, with the tolerance from validation.md |
| `response: str \| None` | `stdout` without the trailing line terminator. `None` if stdout is empty |
| `timed_out: bool` | True if the host reported "no response within the timeout" (the exit code requirements.md assigns to it). A connection problem is not a timeout |

How the host reports errors and timeouts to a CLI user (message text, exit code) is defined in requirements.md. If requirements specify CLI-level behaviour, the `host` fixture will expose it, so check `conftest.py`. Assert on what requirements specify, using exact strings.

`host` runs the real `relay-host` CLI as a subprocess. Tests must still use only the members above, not call the CLI themselves.

## `host_at` and `host_unreachable`

- `host_at(address: str)` is a factory fixture. It returns a host with the same interface as `host` (all members, same `HostResult`), configured with the given address string exactly as given, including invalid or empty values. Use it for address-configuration ACs (e.g. an invalid address). `host` itself is `host_at(<the simulator's serial address>)`.
- `host_unreachable` is a host pointed at a valid address where nothing is listening. Use it for "cannot connect" cases.
- Neither needs a running simulator, and a test using them doesn't need `control`.

## `control`

The simulator's control API, on a separate port. Use it **only** for setup, fault injection and observation. It never sends relay commands, and the host never uses it.

| Method | Purpose |
|---|---|
| `control.set_state(state)` | Put the relay in a starting state. `state` is `<from requirements.md>` |
| `control.get_state()` | Observe the relay's current state, independently of what the host reported |
| `control.fault(enabled: bool = True)` | Inject the fault (`True`) or clear it (`False`). Clearing a fault keeps the relay state. What a faulted device responds is `<from requirements.md>` |
| `control.silence(enabled: bool = True)` | Make the device stop responding to serial input, or resume |
| `control.reset()` | Return to the initial state and clear faults, silence and the clock. The fixtures already do this between tests, so call it only mid-test if a scenario needs it |
| `control.advance_time(seconds: float)` | Move the simulator's clock forward. This is the only way simulated time passes |

Typical uses:
- **Arrange:** `control.set_state(...)` so the test starts where the AC starts.
- **Fault injection:** `control.silence()` for the silent-device case, or `control.fault()` / `control.fault(False)` to inject and clear a fault.
- **Observe:** after acting through `host`, `control.get_state()` confirms the device really changed, not just that the host said so.
- **Time rules:** `host.on()`, then `control.advance_time(1.9)`, then `host.off()`, then assert on the response defined for that case.

## `wait_until`

```python
from tests.e2e.helpers import wait_until

wait_until(condition, timeout, interval=0.05, message=None)
```

- `condition`: a zero-argument callable returning a truthy value when the awaited event has happened.
- `timeout`: seconds of **real** time before failing.
- When it times out it raises `AssertionError` containing `message`, so the failure reads as a test failure, not an error.
- Use it only for real asynchronous events, such as a connection closing or a state change visible via `control.get_state()` after an async operation. Don't use it to let time pass for rules that run on simulated time.

`wait_until` polls internally, which is the one place a short sleep is allowed. Test functions never call `time.sleep`.

## Time: simulated vs real

| What depends on it | Clock | How tests move it |
|---|---|---|
| Simulator rules (rate limit / BUSY window, simulator-side timeouts) | Simulated, injectable | `control.advance_time(seconds)` |
| Network delivery, async completion | Real | `wait_until(...)` |
| Host read timeout (e.g. silent device) | Real (the host is not on the simulator clock) | The `host` fixture never sets a timeout, so the host's default from requirements.md applies. See "Short host timeout" below |

### Short host timeout

- The `host` fixture always uses the host's default read timeout. It never adds `--timeout` by itself.
- **One** shorter value is allowed: `SHORT_TIMEOUT = "0.3"` (seconds), defined in `tests/e2e/helpers.py`. Pass it explicitly: `host.run("--timeout", SHORT_TIMEOUT, "status")`.
- Use it **only** to save time in tests whose AC requires waiting out the timeout against a silent device. In F1 that means F1-AC-15 (including the silent-and-faulted case) and F1-AC-16. Every test that expects a response uses the default.
- A test that checks the default timeout itself (F1-AC-21's default case) must not pass `--timeout`. A value an AC states explicitly (F1-AC-21's `--timeout 0.3`) is used because the AC says so, not as a time saving.
- Any other timeout value, or using `SHORT_TIMEOUT` anywhere else, needs the user's approval first. Ask; don't add it.

## Open points (decide when implementing)

These are not decided yet. Don't hardcode an answer in tests. Ask the user if a test depends on one.
- Exact protocol strings, response format and error codes come from F1's requirements.md.


Decided (2026-11-19):
- The simulator runs in-process on a background thread, on free ports chosen at start-up. Tests still must not depend on this.
- `host` runs the real `relay-host` CLI as a subprocess. The CLI-level fields of `HostResult` are listed in the `host` section.
