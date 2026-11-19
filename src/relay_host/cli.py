"""relay-host: send one command to the relay and report the response (req §4; plan 6.2-6.4)."""
from __future__ import annotations

import argparse
import math
import os
import sys

from .client import (
    ADDRESS_ENV_VAR,
    DEFAULT_ADDRESS,
    DEFAULT_TIMEOUT,
    HostConnectError,
    HostTimeout,
    RelayClient,
)

EXIT_OK = 0
EXIT_DEVICE_ERROR = 1
EXIT_USAGE = 2  # argparse also uses 2 for its own errors
EXIT_NO_RESPONSE = 3
EXIT_CONNECT = 4

COMMANDS = {"on": "ON", "off": "OFF", "status": "STATUS"}


def _timeout(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError(f"must be a finite number greater than 0: {value!r}")
    return seconds


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="relay-host",
        description=(
            "Send one command to the simulated relay. "
            f"The address comes from {ADDRESS_ENV_VAR} (default {DEFAULT_ADDRESS})."
        ),
    )
    parser.add_argument(
        "--timeout", type=_timeout, default=DEFAULT_TIMEOUT, metavar="SECONDS",
        help=f"how long to wait for a response (default {DEFAULT_TIMEOUT})",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="{on,off,status,send,shell}")
    sub.add_parser("on", help="turn the relay on")
    sub.add_parser("off", help="turn the relay off")
    sub.add_parser("status", help="report the relay state")
    send = sub.add_parser("send", help="send a raw line exactly as given")
    send.add_argument("line", help="the line to send (must not contain a newline)")
    sub.add_parser(
        "shell",
        help="type protocol lines (e.g. ON, OFF, STATUS) and see each response",
        description="Each line you type is sent to the device exactly as typed. "
        "Leave with Ctrl+Z then Enter (Windows), Ctrl+D (Linux/macOS), or Ctrl+C.",
    )
    return parser


PROMPT = b"relay> "
UTF8_BOM = b"\xef\xbb\xbf"  # added by Windows PowerShell 5.1 when piping (req §4.4, F1-AC-29)


def _one_line(message: str) -> str:
    return " ".join(message.split())


def run_shell(client: RelayClient) -> int:
    """Interactive shell (req §4.4; plan D9-D11). Returns the shell's exit code."""
    interactive = sys.stdin.isatty()
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    first = True
    try:
        while True:
            if interactive:
                stdout.write(PROMPT)
                stdout.flush()
            raw = stdin.readline()
            if first:
                first = False
                if raw.startswith(UTF8_BOM):
                    raw = raw[len(UTF8_BOM):]  # dropped once, at the very start of input
            if not raw:
                break  # end of input (also when the input was only a byte-order mark)
            if raw.endswith(b"\r\n"):
                raw = raw[:-2]
            elif raw.endswith(b"\n"):
                raw = raw[:-1]
            try:
                response = client.send_bytes(raw)  # one connection per line
            except (HostConnectError, HostTimeout) as exc:
                print(f"relay-host: {_one_line(str(exc))}", file=sys.stderr, flush=True)
                continue
            stdout.write(response.encode("ascii", errors="replace") + b"\n")
            stdout.flush()
    except KeyboardInterrupt:
        if interactive:
            stdout.write(b"\n")
            stdout.flush()
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)  # exits 2 on usage errors, with nothing on stdout

    if args.command == "shell":
        address = os.environ.get(ADDRESS_ENV_VAR, DEFAULT_ADDRESS)
        return run_shell(RelayClient(address, args.timeout))

    if args.command == "send":
        if "\n" in args.line:
            parser.error("the line to send must not contain a newline")
        line = args.line
    else:
        line = COMMANDS[args.command]

    address = os.environ.get(ADDRESS_ENV_VAR, DEFAULT_ADDRESS)
    client = RelayClient(address, args.timeout)
    try:
        response = client.send_line(line)
    except HostConnectError as exc:
        print(f"relay-host: {exc}", file=sys.stderr)
        return EXIT_CONNECT
    except HostTimeout as exc:
        print(f"relay-host: {exc}", file=sys.stderr)
        return EXIT_NO_RESPONSE

    # Write bytes so Windows newline translation can't turn "\n" into "\r\n" (plan 6.3).
    sys.stdout.buffer.write(response.encode("ascii", errors="replace") + b"\n")
    sys.stdout.flush()
    return EXIT_DEVICE_ERROR if response.startswith("ERR ") else EXIT_OK
