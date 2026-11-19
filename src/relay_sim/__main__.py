"""relay-sim: run the simulated relay until Ctrl+C (plan 4.4, D2)."""
from __future__ import annotations

import argparse
import sys
import threading

from .clock import MonotonicClock
from .exchange_log import Entry
from .simulator import DEFAULT_BIND, DEFAULT_CONTROL_PORT, DEFAULT_SERIAL_PORT, Simulator


def _port(value: str) -> int:
    port = int(value)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port out of range: {value}")
    return port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relay-sim", description="Run the simulated relay.")
    parser.add_argument("--bind", default=DEFAULT_BIND, help=f"address to listen on (default {DEFAULT_BIND})")
    parser.add_argument("--port", type=_port, default=DEFAULT_SERIAL_PORT, help=f"serial port (default {DEFAULT_SERIAL_PORT})")
    parser.add_argument(
        "--control-port", type=_port, default=DEFAULT_CONTROL_PORT,
        help=f"control API port, used only by tests (default {DEFAULT_CONTROL_PORT})",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="don't print the exchange log")
    args = parser.parse_args(argv)

    # Run by hand, the simulator follows real time, so toggles 2 s apart work (req §2.6, plan D14).
    clock = MonotonicClock()
    sim = Simulator(bind=args.bind, port=args.port, control_port=args.control_port, clock=clock)
    if not args.quiet:
        def show(entry: Entry) -> None:
            print(entry.format(), flush=True)
        sim.log.subscribe(show)
    try:
        sim.start()
    except OSError as exc:
        print(
            f"relay-sim: cannot listen on {args.bind} ports {args.port}/{args.control_port}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        f"relay-sim: serial on {args.bind}:{sim.serial_port}, control on {args.bind}:{sim.control_port}. "
        "Press Ctrl+C to stop.",
        flush=True,
    )
    stop = threading.Event()
    try:
        while not stop.wait(0.5):  # short waits keep Ctrl+C responsive on Windows
            pass
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop()
    print("relay-sim: stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
