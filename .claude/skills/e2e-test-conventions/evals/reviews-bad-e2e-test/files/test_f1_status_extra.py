import time


def test_status_with_argument(host, control):
    control.set_state("ON")
    time.sleep(0.5)  # give the simulator time to settle
    r = host.send_raw("STATUS now")
    assert "ERR" in r.stdout
    assert r.exit_code != 0


def test_off_works(host, control):
    control.set_state("ON")
    control.set_state("OFF")  # turn the relay off
    assert host.status().stdout == "STATUS OFF\n"
