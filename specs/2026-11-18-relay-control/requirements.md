# F1: Relay control and status - Requirements

**Status:** v1.1, reviewed 2026-11-19 (v1 plus change C1, see "Changes").
**Phase:** 1 (see `specs/roadmap.md`)

> Items marked belong to change C1 and still need review.

## 1. Scope

F1 delivers:
- A simulator that models one relay (`OFF` / `ON`) and speaks a line-based text protocol over serial-over-TCP.
- A host CLI (`relay-host`) that sends one command per run and reports the device's response and an exit code.
- An interactive shell (`relay-host shell`) where the user types protocol lines, such as `ON`, one after another and sees each response (§4.4).
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
| `relay-host shell` | Each line typed in the shell, exactly as typed (§4.4) |

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

This table applies to single-command runs (`on`, `off`, `status`, `send`). The shell has its own exit codes (§4.4).

### 4.4 Interactive shell (`relay-host shell`)

Added by change C1.

**Starting**
- `relay-host [--timeout <seconds>] shell` starts the shell. It uses the same address (`RELAY_HOST_ADDRESS`) and timeout as the other subcommands.
- `shell` takes no arguments. An extra argument is a usage error (exit 2), and nothing is sent to the device.

**Input**
- The shell reads lines from standard input until end of input.
- From each line it removes the line ending (`\n` or `\r\n`). Everything else is sent to the device **exactly as typed**, the same way `send` does (§4.2). So `ON` is accepted, `on` gets `ERR UNKNOWN_CMD`, and an empty line gets `ERR EMPTY`.
- No word is reserved. Every line goes to the device.
- If the input starts with a UTF-8 byte-order mark (bytes `EF BB BF`), the shell drops it before the first line. Windows PowerShell 5.1 adds this mark when it pipes text into a program. Nobody typed it, so it is not part of the line. Only one mark, at the very start of the input, is dropped.

**Connections**
- Each line is handled like one `relay-host send` run: connect, send the line, wait for one response line, disconnect.
- The shell holds no connection while it waits for the next line, so other clients are never blocked by an idle shell.

**Output**
- When the device responds, the shell prints the response unchanged to stdout, followed by exactly one `\n`.
- When there is no response within the timeout, or the shell can't connect (including an invalid address), it prints one short line to stderr and nothing to stdout. Then it continues with the next line.
- When standard input is an interactive terminal, the shell shows the prompt `relay> ` before each line. When input is not a terminal (for example, piped from a file), it shows no prompt.

**Leaving**
- End of input (Ctrl+Z then Enter on Windows, Ctrl+D on Linux/macOS) ends the shell with exit code **0**.
- Ctrl+C also ends it, with exit code 0 and no error trace.
- The exit code doesn't depend on the responses received during the session.

| Shell exit code | Meaning |
|---|---|
| 0 | The shell ended normally (end of input or Ctrl+C) |
| 2 | Usage error when starting the shell. Nothing is sent to the device |

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

### Interactive shell (change C1)

In these ACs the shell's input is given as text on standard input (not a terminal), so no prompt is shown (§4.4).

- **F1-AC-24 The shell sends each line as typed and prints each response.** From `OFF`, `relay-host shell` with the input lines `ON`, `STATUS`, `on` and an empty line:
  - prints exactly `OK\nSTATUS ON\nERR UNKNOWN_CMD\nERR EMPTY\n` to stdout,
  - exits 0 at the end of input,
  - leaves the state `ON`.
- **F1-AC-25 A line without a response doesn't end the shell.**
  - With silence on, `relay-host shell` with the input lines `STATUS` and `STATUS` prints nothing to stdout, prints one line to stderr for each input line (two lines), and exits 0.
  - The same holds when no simulator is listening at the address in `RELAY_HOST_ADDRESS`.
- **F1-AC-26 An idle shell doesn't block other clients.** A shell gets the input line `STATUS` and prints `STATUS OFF`. While it then waits for the next line, `relay-host status` prints `STATUS OFF` and exits 0. At end of input, the shell exits 0, and its whole stdout is exactly `STATUS OFF\n`.
- **F1-AC-27 End of input ends the shell without sending anything.** `relay-host shell` with empty input prints nothing to stdout and exits 0, and the simulator receives nothing.
- **F1-AC-28 An extra argument to `shell` is a usage error.** `relay-host shell ON` exits 2, prints nothing to stdout, and the simulator receives nothing.
- **F1-AC-29 A leading byte-order mark is dropped.** From `OFF`, `relay-host shell` with input that starts with the UTF-8 byte-order mark followed by the lines `ON` and `STATUS`:
  - prints exactly `OK\nSTATUS ON\n`,
  - exits 0,
  - and the simulator receives `ON` (without the mark) and `STATUS`.

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
| Shell: lowercase line, empty line | Sent unchanged: `ERR UNKNOWN_CMD`, `ERR EMPTY` | F1-AC-24 |
| Shell: silent device or no simulator | One stderr line per input line, shell continues, exit 0 | F1-AC-25 |
| Shell: idle while another client connects | The other client is served | F1-AC-26 |
| Shell: empty input | Exit 0, nothing sent | F1-AC-27 |
| Shell: input piped from Windows PowerShell 5.1 (starts with a UTF-8 byte-order mark) | The mark is dropped and the first line is handled normally | F1-AC-29 |
| Shell: prompt and Ctrl+C | Prompt only on a terminal; Ctrl+C exits 0 | none (needs a real terminal; checked by hand) |
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
- **Why the shell sends raw lines and connects per line (C1).** The shell exists so a person can type protocol commands such as `ON` directly, without `relay-host` in front of each one. Sending lines unchanged keeps the protocol rules visible (`on` is still rejected) and reuses `send`'s behaviour. Connecting per line keeps the simulator's single connection free between lines, so tests and other `relay-host` runs work while a shell is open. Keeping a connection open was rejected for that reason.

## 10. Open questions

None.

## Changes

### C1 (2026-11-19): interactive shell for the host

- **Reason:** the user wants to type protocol commands such as `ON` directly, instead of running `relay-host on` for each command.
- **Decided with the user:** lines are sent exactly as typed, the shell connects once per line, and it ends on end of input or Ctrl+C. No quit word is reserved. The rest of §4.4 was proposed by Claude and approved on 2026-11-19.
- **Added:** §1 scope bullet, the `shell` row in §4.1, §4.4, F1-AC-24 … F1-AC-29, §7 rows, and a §9 design note.
- **Changed:** §4.3 now says its exit-code table covers single-command runs only. The behaviour of `on`, `off`, `status` and `send` is unchanged.
- **Existing ACs:** F1-AC-01 … F1-AC-23 are unchanged, so no existing test changes.
- **Amended during planning (2026-11-19, approved by the user):** F1-AC-26 now has the shell handle one line before the other client runs. A handled line is the only observable proof that the shell is running and waiting, not still starting.
- **Amended during implementation (2026-11-19, approved by the user):** the shell drops a UTF-8 byte-order mark at the very start of its input (§4.4), with the new F1-AC-29 and a §7 row. Found while checking the README example: Windows PowerShell 5.1 adds the mark when piping, so the first piped line got `ERR UNKNOWN_CMD`.
