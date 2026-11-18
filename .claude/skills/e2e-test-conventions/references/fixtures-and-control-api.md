# Fixtures, control API and helpers: the contract (v1)

This file defines the interface that E2E tests may rely on. `tests/e2e/conftest.py` and `tests/e2e/helpers.py` don't exist yet. When they are implemented they must match this contract, and if a change is needed this file is updated first.

Values such as relay states, fault names, command strings and response text are **not** defined here. They come from the feature's `requirements.md`. Where this file says `<from requirements.md>`, copy the value from there.

## Contents
- `simulator`
- `host`
- `control`
- `wait_until`
- Time: simulated vs real
- Open points (decide when implementing)

---

## `simulator`

- Each test gets either a fresh simulator instance or a shared one reset to its initial state. Either way, no state leaks between tests, and tests pass in any order and in isolation (`pytest path::test_name`).
- Whether it runs as a thread or a subprocess is an implementation detail. Tests must not depend on it.
- Tests normally don't use `simulator` directly. `host` and `control` depend on it. Request it explicitly only when a test needs something it exposes, such as the serial endpoint for a raw-connection test, if requirements call for one.
- The fixture also starts the exchange-log capture that ends up in the pytest-html report. Tests don't log anything themselves.

## `host`

The host utility, already connected to the simulator over serial-over-TCP. Every relay command goes through it.

| Member | Meaning |
|---|---|
| `host.on()` | Send the "relay on" command as defined in requirements.md |
| `host.off()` | Send the "relay off" command |
| `host.status()` | Send the status query |
| `host.send_raw(line: str)` | Send `line` exactly as given (plus the line terminator the protocol defines). Use it for negative and edge cases: unknown command, lowercase, empty line, extra whitespace |

Each call returns a `HostResult`:

| Field | Meaning |
|---|---|
| `response: str \| None` | The device's response as received, without the line terminator. `None` if nothing arrived before the host's read timeout |
| `timed_out: bool` | True if the host gave up waiting for a response |

How the host reports errors and timeouts to a CLI user (message text, exit code) is defined in requirements.md. If requirements specify CLI-level behaviour, the `host` fixture will expose it, so check `conftest.py`. Assert on what requirements specify, using exact strings.

Whether `host` wraps the `relay-host` CLI or the client library is not decided yet. Tests must use only the members above.

## `control`

The simulator's control API, on a separate port. Use it **only** for setup, fault injection and observation. It never sends relay commands, and the host never uses it.

| Method | Purpose |
|---|---|
| `control.set_state(state)` | Put the relay in a starting state. `state` is `<from requirements.md>` |
| `control.get_state()` | Observe the relay's current state, independently of what the host reported |
| `control.inject_fault(fault)` | Put the device into a fault state. `fault` is `<from requirements.md>` |
| `control.silence(enabled: bool = True)` | Make the device stop responding to serial input, or resume |
| `control.reset()` | Return to the initial state and clear faults, silence and the clock. The fixtures already do this between tests, so call it only mid-test if a scenario needs it |
| `control.advance_time(seconds: float)` | Move the simulator's clock forward. This is the only way simulated time passes |

Typical uses:
- **Arrange:** `control.set_state(...)` so the test starts where the AC starts.
- **Fault injection:** `control.silence()` for the silent-device case, or `control.inject_fault(...)`.
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
| Host read timeout (e.g. silent device) | Real (the host is not on the simulator clock) | The `host` fixture sets a short timeout. The test just calls `host.status()` and checks `timed_out` |

## Open points (decide when implementing)

These are not decided yet. Don't hardcode an answer in tests. Ask the user if a test depends on one.
- Exact protocol strings, response format and error codes come from F1's requirements.md.
- Whether the simulator runs as a thread or a subprocess.
- Whether `host` wraps the CLI or the client library, and any CLI-level fields on `HostResult`.
- The host read timeout value used in tests, and whether requirements fix a value.
