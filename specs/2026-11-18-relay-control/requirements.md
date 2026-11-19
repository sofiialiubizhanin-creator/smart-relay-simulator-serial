# F1: Relay control and status - Requirements

**Status:** v1, reviewed 2026-11-19.
**Phase:** 1 (see `specs/roadmap.md`)

## 1. Scope

F1 delivers:
- A simulator that models one relay (`OFF` / `ON`) and speaks a line-based text protocol over serial-over-TCP.
- A host CLI (`relay-host`) that sends one command per run and reports the device's response and an exit code.
- A control API, used only by tests, to set up conditions, inject faults, silence the device, reset it and observe its state.
- The commands `ON`, `OFF` and `STATUS`, with error handling for invalid input, faults and a silent device.

## 2. Protocol (host ↔ simulator)

### 2.1 Encoding and framing
- Commands and responses are ASCII. Any byte above `0x7F` in a line makes it an unknown command (§3).
- One command per line. A line ends with `\n`.
- A trailing `\r` right before `\n` is removed and ignored. A `\r` anywhere else is part of the line.
- Each response is exactly one line ending with `\n`.

### 2.2 Commands
| Command | Effect | Response |
|---|---|---|
| `ON` | Relay goes to `ON` | `OK` |
| `OFF` | Relay goes to `OFF` | `OK` |
| `STATUS` | No state change | `STATUS ON` or `STATUS OFF` |

- Commands are uppercase only and take no arguments. Any other line is an error (§3).
- `ON` when already `ON` responds `OK`, and the state doesn't change.
- `OFF` when already `OFF` responds `OK`, and the state doesn't change.

### 2.3 Initial state
The relay is `OFF` when the simulator starts and after a control-API reset.

### 2.4 Line length limit
- A line's maximum length is **32 bytes**, measured after the `\n` and the trailing `\r` are removed. So 32 bytes followed by `\r\n` is within the limit.
- A line of 33 bytes or more gets `ERR TOO_LONG`.
- Once a line is over the limit, the simulator discards everything up to the next `\n` and then sends exactly one `ERR TOO_LONG`.
- Design constraint (not tested end to end): a very long line must not make the simulator use unbounded memory.

### 2.5 Precedence
When several conditions apply to one line, the first match in this list decides the outcome:

1. **Silent**: no processing and no response.
2. **Fault**: `ERR FAULT`, whatever the line contains, including empty, too-long and unknown lines.
3. **Too long**: `ERR TOO_LONG`.
4. **Empty**: `ERR EMPTY`.
5. **Unknown**: `ERR UNKNOWN_CMD`.
6. **Valid command**: handled as in §2.2.

An error response never changes the relay state.

## 3. Error codes

| Response | When |
|---|---|
| `ERR UNKNOWN_CMD` | The line isn't exactly `ON`, `OFF` or `STATUS`. Examples: lowercase or mixed case, leading or trailing spaces or tabs, arguments, unknown words, any byte above `0x7F` |
| `ERR EMPTY` | The line is empty, including a line that is only `\r` |
| `ERR TOO_LONG` | The line is longer than 32 bytes (§2.4) |
| `ERR FAULT` | A fault is injected. Every line gets this response (§2.5) |

## 4. Host CLI (`relay-host`)

### 4.1 Subcommands and configuration
| Invocation | Line sent to the device |
|---|---|
| `relay-host on` | `ON` |
| `relay-host off` | `OFF` |
| `relay-host status` | `STATUS` |
| `relay-host send "<raw line>"` | `<raw line>` exactly as given |

- Option: `--timeout <seconds>`, default **1.0**. It must be a finite number greater than 0.
- Address: the host reads the simulator's address from the `RELAY_HOST_ADDRESS` environment variable and uses `127.0.0.1:5555` when the variable isn't set. There is no address CLI option.
- A valid address is `HOST:PORT`: `HOST` is a non-empty hostname or IPv4 address, and `PORT` is a decimal integer from 1 to 65535. IPv6 isn't supported. A variable that is set but empty is invalid. An invalid address is treated as "cannot connect" (exit 4).
- Each run connects, sends one line, waits for one response line, and disconnects.

### 4.2 `send` is transparent
- `send` doesn't trim, change case, check length or block empty input. The line reaches the device exactly as typed.
- Non-ASCII characters in the argument are sent as their UTF-8 bytes, so the device sees them and rejects the line (§3).
- The only exception is a raw line containing `\n`, which is a usage error (exit 2), because it would be more than one command.
- Why this matters is explained in §9.

### 4.3 Output and exit codes
- When the device responds, the host prints the response unchanged to stdout, followed by exactly one `\n`.
- For exit codes 2, 3 and 4, nothing goes to stdout and a short message goes to stderr.

| Exit code | Meaning |
|---|---|
| 0 | The device responded with something other than an error (`OK`, `STATUS ON`, `STATUS OFF`) |
| 1 | The device responded with `ERR <CODE>` |
| 2 | CLI usage error: unknown subcommand, missing or extra arguments, `send` line containing `\n`, invalid `--timeout` (§4.1). Nothing is sent to the device |
| 3 | No response within the timeout |
| 4 | Cannot connect to the simulator, including an invalid `RELAY_HOST_ADDRESS` (§4.1) |

## 5. Control API (tests only)

The control API runs on a separate TCP port and uses simple text commands. Only tests use it. The host never does. The exact wire format is defined in plan.md.

| Capability | Command | Behaviour |
|---|---|---|
| Set relay state | `SET_STATE ON\|OFF` | Sets the relay state directly, without sending a protocol command |
| Inject / clear fault | `FAULT ON\|OFF` | `ON`: every line gets `ERR FAULT`. `OFF`: clears the fault and keeps the relay state |
| Silence device | `SILENCE ON\|OFF` | `ON`: the device reads lines but doesn't process them or respond. `OFF`: it responds again. Lines received while silent are dropped, not replayed |
| Reset | `RESET` | Relay `OFF`, fault cleared, silence cleared, simulated clock reset |
| Advance time | `ADVANCE_TIME <sec>` | Moves the simulated clock forward. No F1 behaviour depends on time; Phase 2 uses it |
| Observe state | `GET_STATE` | Returns the current relay state (`ON` / `OFF`) |

## 6. Acceptance Criteria

Each AC must be observable through the host (`relay-host`).
- "State" means the relay state observed through the control API (`GET_STATE`).
- "The simulator receives" or "sends" means the simulator's exchange log for the test.
- **Notation:** in AC arguments, `\r`, `\t` and `\n` stand for the actual control characters (CR, TAB, LF) inside the argument passed to `relay-host`. The host doesn't interpret escape sequences. `<N bytes>` means an ASCII line of exactly N bytes that isn't a command (for example `X` repeated N times).

### Relay control
- **F1-AC-01 Initial state is OFF.** After the simulator starts or is reset, `relay-host status` prints `STATUS OFF` and exits 0.
- **F1-AC-02 ON turns the relay on.** From `OFF`, `relay-host on` prints `OK` and exits 0. The state is `ON`.
- **F1-AC-03 OFF turns the relay off.** From `ON`, `relay-host off` prints `OK` and exits 0. The state is `OFF`.
- **F1-AC-04 STATUS reports the state without changing it.** When the state is `ON`, `relay-host status` prints `STATUS ON` and exits 0. The state is still `ON`.
- **F1-AC-05 Repeated ON is accepted and changes nothing.** When the state is `ON`, `relay-host on` prints `OK` and exits 0. The state is still `ON`.
- **F1-AC-06 Repeated OFF is accepted and changes nothing.** When the state is `OFF`, `relay-host off` prints `OK` and exits 0. The state is still `OFF`.
- **F1-AC-07 A trailing CR is ignored.** From `OFF`, `relay-host send "ON\r"` prints `OK`, exits 0, and the state is `ON`. Then `relay-host send "STATUS\r"` prints `STATUS ON` and exits 0.

### Input errors
- **F1-AC-08 Lowercase is rejected.** `relay-host send` with each of `on`, `On`, `oN`, `off`, `Off`, `status` and `Status` prints `ERR UNKNOWN_CMD` and exits 1. The state doesn't change.
- **F1-AC-09 Extra whitespace or arguments are rejected.** `send " ON"`, `send "ON "`, `send "ON 1"` and `send "\tSTATUS"` each print `ERR UNKNOWN_CMD` and exit 1. The state doesn't change.
- **F1-AC-10 Unknown commands are rejected.** `send "TOGGLE"` and `send "ÖN"` (sent as the UTF-8 bytes `C3 96 4E`) each print `ERR UNKNOWN_CMD` and exit 1. The state doesn't change.
- **F1-AC-11 An empty line is rejected.** `relay-host send ""` and `send "\r"` print `ERR EMPTY` and exit 1. The state doesn't change.
- **F1-AC-12 The line length limit is enforced.** From `OFF`:
  - `send "<33 bytes>"` prints `ERR TOO_LONG` and exits 1.
  - `send "<10000 bytes>"` prints `ERR TOO_LONG` and exits 1, and the simulator sends exactly one response for that line.
  - `send "<32 bytes>"` and `send "<32 bytes>\r"` each print `ERR UNKNOWN_CMD`, not `ERR TOO_LONG`, and exit 1.
  - After each of these, the state is still `OFF`, and `relay-host status` prints `STATUS OFF` and exits 0.

### Fault, silence, reset
- **F1-AC-13 A faulted device rejects everything.** With a fault injected, `on`, `off`, `status`, and `send` with `TOGGLE`, an empty line or `<33 bytes>` each print `ERR FAULT` and exit 1. The state doesn't change.
- **F1-AC-14 Clearing the fault restores normal operation.** From `ON`, after `FAULT ON` then `FAULT OFF`:
  - The state is still `ON`.
  - `relay-host status` prints `STATUS ON` and exits 0.
  - `relay-host off` prints `OK` and exits 0, and the state becomes `OFF`.
- **F1-AC-15 A silent device doesn't respond.** With silence on, `relay-host on` prints nothing to stdout and exits 3 once the timeout passes. The state doesn't change. The same holds when a fault is also injected (silence wins, §2.5).
- **F1-AC-16 Ending silence restores operation without replay.** From `OFF` with silence on, `relay-host on` exits 3. After `SILENCE OFF`, the state is still `OFF` (the `ON` was never executed), and `relay-host status` prints `STATUS OFF` and exits 0.
- **F1-AC-17 Reset restores the initial condition.** After `RESET`, starting from state `ON` with fault and silence active, `relay-host status` prints `STATUS OFF` and exits 0.

### Host CLI
- **F1-AC-18 `send` delivers the line unchanged.** `relay-host send "STATUS"` gives the same stdout and exit code as `relay-host status`. `send "on"` gets `ERR UNKNOWN_CMD`, not `OK`, which shows that the host didn't change the case.
- **F1-AC-19 The output is the device response, unchanged.** For each device response (`OK`, `STATUS ON`, `STATUS OFF`, `ERR UNKNOWN_CMD`, `ERR EMPTY`, `ERR TOO_LONG`, `ERR FAULT`), stdout is exactly that response followed by one `\n`. The exit code is 0 for `OK` and `STATUS …`, and 1 for `ERR …`.
- **F1-AC-20 Usage errors exit 2 and send nothing.** Each of these exits 2, prints nothing to stdout, and leaves the state unchanged, and the simulator receives nothing:
  - an unknown subcommand,
  - a missing `send` argument,
  - extra arguments,
  - a `send` line containing `\n`,
  - an invalid `--timeout` (`0`, `-1`, `abc`, `nan`).
- **F1-AC-21 The timeout defaults to 1.0 s and can be configured.** Against a silent device:
  - `relay-host status` with no `--timeout` exits 3 after 1.0 s.
  - `relay-host --timeout 0.3 status` exits 3 after 0.3 s.
  - Both durations are checked within the tolerance defined in validation.md.
- **F1-AC-22 A connection failure exits 4.** When no simulator is listening at the address in `RELAY_HOST_ADDRESS`, `relay-host status` exits 4 and prints nothing to stdout.
- **F1-AC-23 An invalid address exits 4.** With `RELAY_HOST_ADDRESS` set to `127.0.0.1` (no port), `127.0.0.1:abc`, `127.0.0.1:0` or an empty string, `relay-host status` exits 4 and prints nothing to stdout.

## 7. Edge cases

| Case | Expected behaviour | AC |
|---|---|---|
| Lowercase or mixed-case command | `ERR UNKNOWN_CMD` | F1-AC-08 |
| Leading or trailing spaces, tabs, arguments | `ERR UNKNOWN_CMD` | F1-AC-09 |
| Non-ASCII bytes | `ERR UNKNOWN_CMD` | F1-AC-10 |
| Empty line, or `\r` only | `ERR EMPTY` | F1-AC-11 |
| 32 bytes, 32 bytes + `\r`, 33 bytes | Within the limit / within the limit / `ERR TOO_LONG` | F1-AC-12 |
| 10 000-byte line | Exactly one `ERR TOO_LONG`, rest discarded | F1-AC-12 |
| Repeated `ON` / repeated `OFF` | `OK`, state unchanged | F1-AC-05, F1-AC-06 |
| Fault active, any line | `ERR FAULT` | F1-AC-13 |
| Silent device | No response, host exit 3, state unchanged | F1-AC-15 |
| Silent and faulted together | Silence wins: no response | F1-AC-15 |
| Invalid `RELAY_HOST_ADDRESS` | Exit 4 | F1-AC-23 |
| Connection closed before `\n` | Partial line discarded, no response | none (not tested end to end: the host always ends a line with `\n`) |

## 8. Out of scope

The simulator doesn't model:
- Electrical behaviour or contact bounce.
- More than one relay.
- Real serial settings (baud rate, parity, etc.).
- Several hosts connected at the same time.
- Keeping state across simulator restarts.
- Authentication.

Also not in F1:
- `ERR BUSY` and the toggle rate limit (Phase 2).
- What the host does if the device closes the connection after the command is sent and before it responds.

## 9. Design notes (rationale to remember)

- **Why `relay-host send` exists.** The edge cases (lowercase, empty line, unknown command, extra whitespace, too-long line) must be tested end to end through the host, not by talking to the simulator directly. A host with only `on`, `off` and `status` would never send `on` or an empty line, so those cases couldn't be tested. `send` passes a raw line straight to the device, so it must not change it in any way (§4.2).
- **Why a repeated `ON` is not a toggle.** A repeated `ON` responds `OK` without changing the state. In Phase 2 the rate limit (`BUSY`) applies only to toggles, meaning commands that change the state, so a repeated `ON` doesn't count towards `BUSY`. This keeps Phase 2's rule simple.

## 10. Open questions

None.

## Changes

None yet. This is the first version.
