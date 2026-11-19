"""Component tests for the control API and ControlClient (plan 5). Not AC coverage."""
import socket

import pytest

from relay_sim.exchange_log import TX
from relay_sim.simulator import Simulator
from tests.e2e.helpers import ControlClient, ControlError


@pytest.fixture
def sim():
    with Simulator(port=0, control_port=0) as s:
        yield s


@pytest.fixture
def control(sim):
    with ControlClient(sim.control_port) as c:
        yield c


def serial_exchange(sim, line: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", sim.serial_port), timeout=2) as sock:
        sock.sendall(line + b"\n")
        with sock.makefile("rb") as replies:
            return replies.readline()


def test_get_state_and_set_state(sim, control):
    assert control.get_state() == "OFF"
    control.set_state("ON")
    assert control.get_state() == "ON"
    assert sim.device.get_state() == "ON"
    assert serial_exchange(sim, b"STATUS") == b"STATUS ON\n"


def test_get_state_sees_serial_commands(sim, control):
    serial_exchange(sim, b"ON")
    assert control.get_state() == "ON"


def test_fault_on_and_off_keeps_state(sim, control):
    control.set_state("ON")
    control.fault()
    assert serial_exchange(sim, b"STATUS") == b"ERR FAULT\n"
    control.fault(False)
    assert control.get_state() == "ON"
    assert serial_exchange(sim, b"STATUS") == b"STATUS ON\n"


def test_silence_on_and_off(sim, control):
    control.silence()
    assert sim.device.silent
    control.silence(False)
    assert not sim.device.silent
    assert serial_exchange(sim, b"STATUS") == b"STATUS OFF\n"


def test_reset_restores_everything_and_clears_log(sim, control):
    serial_exchange(sim, b"ON")
    control.fault()
    control.silence()
    control.advance_time(7)
    assert sim.log.entries()
    control.reset()
    d = sim.device
    assert (d.get_state(), d.fault, d.silent, d.clock.now()) == ("OFF", False, False, 0.0)
    assert sim.log.entries() == []


def test_advance_time_moves_simulated_clock(sim, control):
    control.advance_time(1.5)
    control.advance_time(0.25)
    assert sim.device.clock.now() == 1.75
    control.advance_time(0)
    assert sim.device.clock.now() == 1.75


@pytest.mark.parametrize(
    "line",
    [
        "BOGUS", "get_state", "GET_STATE now", "RESET 1",
        "SET_STATE", "SET_STATE on", "SET_STATE ON OFF", "SET_STATE MAYBE",
        "FAULT", "FAULT yes", "SILENCE 1",
        "ADVANCE_TIME", "ADVANCE_TIME -1", "ADVANCE_TIME abc", "ADVANCE_TIME nan", "ADVANCE_TIME inf",
        "",
    ],
)
def test_bad_commands_answer_err_and_change_nothing(sim, control, line):
    with pytest.raises(ControlError, match="ERR"):
        control.command(line)
    d = sim.device
    assert (d.get_state(), d.fault, d.silent, d.clock.now()) == ("OFF", False, False, 0.0)
    assert control.get_state() == "OFF"  # connection still usable


def test_raw_wire_format(sim):
    with socket.create_connection(("127.0.0.1", sim.control_port), timeout=2) as sock:
        sock.sendall(b"SET_STATE ON\r\nGET_STATE\nBOGUS\n" + b"Z" * 300 + b"\nGET_STATE\n")
        f = sock.makefile("rb")
        assert [f.readline() for _ in range(5)] == [
            b"OK\n", b"ON\n", b"ERR unknown command 'BOGUS'\n", b"ERR line too long\n", b"ON\n",
        ]


def test_several_control_clients_at_once(sim, control):
    with ControlClient(sim.control_port) as second:
        control.set_state("ON")
        assert second.get_state() == "ON"


def test_control_traffic_is_not_in_exchange_log(sim, control):
    control.set_state("ON")
    control.get_state()
    assert sim.log.entries() == []
    serial_exchange(sim, b"STATUS")
    assert [(e.direction, e.data) for e in sim.log.entries() if e.direction == TX] == [(TX, b"STATUS ON")]


def test_serial_port_does_not_accept_control_commands(sim):
    assert serial_exchange(sim, b"SET_STATE ON") == b"ERR UNKNOWN_CMD\n"
    assert sim.device.get_state() == "OFF"


def test_stop_returns_while_control_client_connected():
    sim = Simulator(port=0, control_port=0).start()
    client = ControlClient(sim.control_port)
    try:
        sim.stop()
    finally:
        client.close()


def test_busy_port_fails_start_cleanly():
    with Simulator(port=0, control_port=0) as first:
        taken = first.control_port
        second = Simulator(port=0, control_port=taken)
        with pytest.raises(OSError):
            second.start()
