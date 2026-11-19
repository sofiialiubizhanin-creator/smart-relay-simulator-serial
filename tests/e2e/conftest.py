"""E2E fixtures and exchange-log reporting (plan §7, D6, D8).

Contract: .claude/skills/e2e-test-conventions/references/fixtures-and-control-api.md

- One simulator per session (in-process thread, free ports), RESET before each test.
- `host` runs the real relay-host CLI as a subprocess.
- Every test's host runs and simulator RX/TX entries, with timestamps, are written to
  the pytest-html report and to reports/exchange.log, whether the test passes or fails.
"""
from __future__ import annotations

import html
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import pytest

from relay_sim.simulator import Simulator
from tests.e2e.helpers import ControlClient, HostResult

_SRC = str(Path(__file__).resolve().parents[2] / "src")
_HOST_PROCESS_TIMEOUT = 60  # safety net only; the host's own timeout ends a run long before this

_runs_key = pytest.StashKey[list]()
_sim_key = pytest.StashKey[Simulator]()
_log_started_key = pytest.StashKey[bool]()


# --- host ------------------------------------------------------------------------------

@dataclass
class _HostRun:
    address: str
    args: tuple[str, ...]
    start: datetime
    end: datetime
    result: HostResult
    stdin: str | None = None  # shell runs only


def _host_env(address: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("RELAY_HOST_ADDRESS", "PYTHONPATH")}
    env["RELAY_HOST_ADDRESS"] = address
    env["PYTHONPATH"] = _SRC
    return env


def _decode(data: bytes) -> str:
    # Decoded without newline translation, so a "\r\n" would stay visible.
    return data.decode("utf-8", errors="backslashreplace")


class ShellSession:
    """A running `relay-host shell` whose stdin stays open until finish()."""

    def __init__(self, host: "Host", args: tuple[str, ...]) -> None:
        self._host = host
        self._args = (*args, "shell")
        self._stdin_text = ""
        self._start = datetime.now().astimezone()
        self._t0 = time.perf_counter()
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "relay_host", *self._args],
            env=_host_env(host.address),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.finished = False

    def write(self, text: str) -> None:
        self._stdin_text += text
        self._proc.stdin.write(text.encode("utf-8"))
        self._proc.stdin.flush()

    def finish(self, input: str = "") -> HostResult:
        if self.finished:
            raise RuntimeError("ShellSession.finish() was already called")
        self._stdin_text += input
        out, err = self._proc.communicate(input.encode("utf-8"), timeout=_HOST_PROCESS_TIMEOUT)
        # Marked only after a clean exit, so a timed-out shell is still killed at teardown.
        self.finished = True
        result = HostResult(self._proc.returncode, _decode(out), _decode(err), time.perf_counter() - self._t0)
        self._host._runs.append(
            _HostRun(self._host.address, self._args, self._start, datetime.now().astimezone(), result, self._stdin_text)
        )
        return result

    def kill(self) -> None:
        if self._proc.poll() is None:
            self._proc.kill()
        self._proc.communicate()  # waits, and closes the stdin/stdout/stderr pipes


@dataclass
class Host:
    """The host utility. Same interface for `host`, `host_at(...)` and `host_unreachable`."""

    address: str
    _runs: list = field(repr=False)
    _sessions: list = field(repr=False, default_factory=list)

    def on(self) -> HostResult:
        return self.run("on")

    def off(self) -> HostResult:
        return self.run("off")

    def status(self) -> HostResult:
        return self.run("status")

    def send_raw(self, line: str) -> HostResult:
        # "--" ends option parsing, so a line starting with "-" still reaches the device unchanged.
        return self.run("send", "--", line)

    def run(self, *args: str) -> HostResult:
        start = datetime.now().astimezone()
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "relay_host", *args],
            env=_host_env(self.address),
            capture_output=True,
            timeout=_HOST_PROCESS_TIMEOUT,
        )
        elapsed = time.perf_counter() - t0
        result = HostResult(proc.returncode, _decode(proc.stdout), _decode(proc.stderr), elapsed)
        self._runs.append(_HostRun(self.address, args, start, datetime.now().astimezone(), result))
        return result

    def shell(self, input: str, *args: str) -> HostResult:
        return self.open_shell(*args).finish(input)

    def open_shell(self, *args: str) -> ShellSession:
        session = ShellSession(self, args)
        self._sessions.append(session)
        return session


@pytest.fixture
def host_at(request):
    runs = request.node.stash.setdefault(_runs_key, [])
    hosts: list[Host] = []

    def make(address: str) -> Host:
        h = Host(address, runs)
        hosts.append(h)
        return h

    yield make
    for h in hosts:  # end any shell a test left unfinished
        for s in h._sessions:
            if not s.finished:
                s.kill()


@pytest.fixture
def host(simulator, host_at) -> Host:
    return host_at(f"127.0.0.1:{simulator.serial_port}")


@pytest.fixture
def host_unreachable(host_at) -> Host:
    with socket.socket() as s:  # bind then release: nothing listens there afterwards
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return host_at(f"127.0.0.1:{port}")


# --- simulator and control -------------------------------------------------------------

@pytest.fixture(scope="session")
def _session_simulator():
    with Simulator(port=0, control_port=0) as sim:
        with ControlClient(sim.control_port) as resetter:
            yield sim, resetter


class SimulatorHandle:
    """What tests may use from the simulator (read-only)."""

    def __init__(self, sim: Simulator) -> None:
        self._sim = sim
        self.serial_port = sim.serial_port
        self.control_port = sim.control_port

    def exchange_log(self) -> list[tuple[datetime, str, bytes]]:
        return [tuple(e) for e in self._sim.log.entries()]


@pytest.fixture
def simulator(_session_simulator, request) -> SimulatorHandle:
    sim, resetter = _session_simulator
    resetter.reset()  # initial state, no fault, not silent, clock 0, empty exchange log
    request.node.stash[_sim_key] = sim  # lets the report hook read this test's log
    return SimulatorHandle(sim)


@pytest.fixture
def control(simulator):
    with ControlClient(simulator.control_port) as client:
        yield client


# --- reporting -------------------------------------------------------------------------

def _show(data: bytes) -> str:
    return '"' + repr(data)[2:-1] + '"'


def _ts(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds")


def _render(item: pytest.Item) -> str | None:
    runs: list[_HostRun] = item.stash.get(_runs_key, [])
    sim = item.stash.get(_sim_key, None)
    entries = sim.log.entries() if sim is not None else []
    if not runs and not entries:
        return None

    timeline: list[tuple[datetime, int, str]] = []
    for n, r in enumerate(sorted(runs, key=lambda r: r.start), 1):  # shells are recorded at finish
        argv = " ".join(["relay-host", *(_show(a.encode("utf-8")) for a in r.args)])
        stdin = f"  stdin={_show(r.stdin.encode('utf-8'))}" if r.stdin is not None else ""
        timeline.append((
            r.start, 0,
            f"{_ts(r.start)} HOST#{n} start  {argv}  [RELAY_HOST_ADDRESS={_show(r.address.encode())}]{stdin}",
        ))
        res = r.result
        timeline.append((
            r.end, 2,
            f"{_ts(r.end)} HOST#{n} exit {res.exit_code} after {res.elapsed:.3f} s"
            f"  stdout={_show(res.stdout.encode('utf-8'))}  stderr={_show(res.stderr.encode('utf-8'))}",
        ))
    for e in entries:
        timeline.append((e.timestamp, 1, f"{_ts(e.timestamp)} SIM {e.direction}  {_show(e.data)}"))
    timeline.sort(key=lambda x: (x[0], x[1]))

    header = "Exchange log (SIM RX = received by the simulator, SIM TX = sent by it)"
    return "\n".join([header, *(line for _, _, line in timeline)])


def _exchange_log_path(config: pytest.Config) -> Path:
    htmlpath = getattr(config.option, "htmlpath", None)
    base = Path(htmlpath).parent if htmlpath else Path("reports")
    if not base.is_absolute():
        base = config.rootpath / base
    return base / "exchange.log"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()
    # Capture once per test: after the test body, or at setup if setup itself failed.
    if not (report.when == "call" or (report.when == "setup" and report.failed)):
        return
    text = _render(item)
    if text is None:
        return

    try:
        import pytest_html

        report.extras = [*getattr(report, "extras", []), pytest_html.extras.html(f"<pre>{html.escape(text)}</pre>")]
    except ImportError:
        pass

    path = _exchange_log_path(item.config)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = not item.config.stash.get(_log_started_key, False)
    item.config.stash[_log_started_key] = True
    with path.open("w" if first else "a", encoding="utf-8", newline="\n") as f:
        f.write(f"===== {item.nodeid} [{report.outcome}] =====\n{text}\n\n")
