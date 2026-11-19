"""Automated check that the E2E exchange log reaches reports/ (plan 7.4, D8). Not AC coverage.

Runs a tiny E2E session in a temporary directory with the real E2E fixtures, then
inspects the report.html and exchange.log it produced.
"""
import html
import re

import pytest

TS = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}[+-]\d\d:\d\d"


@pytest.fixture
def probe_session(pytester):
    pytester.makeconftest('pytest_plugins = ["tests.e2e.conftest"]')
    pytester.makepyfile(
        test_probe="""
        def test_probe_passes(host):
            assert host.status().exit_code == 0

        def test_probe_fails(host):
            host.send_raw("on")
            assert False, "deliberate failure"
        """
    )
    result = pytester.runpytest("--html=reports/report.html", "--self-contained-html", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1, failed=1)
    reports = pytester.path / "reports"
    return (
        (reports / "exchange.log").read_text(encoding="utf-8"),
        _unescape((reports / "report.html").read_text(encoding="utf-8")),
    )


def _unescape(text: str) -> str:
    for _ in range(3):  # the log is HTML-escaped inside pytest-html's JSON data
        text = html.unescape(text)
    return text


def _expected_lines(sent: str, received: str) -> list[str]:
    return [
        rf"{TS} HOST#1 start  relay-host .*",
        rf'{TS} SIM RX  "{sent}"',
        rf'{TS} SIM TX  "{received}"',
        rf"{TS} HOST#1 exit \d after [\d.]+ s  stdout=.*",
    ]


@pytest.mark.parametrize("which", ["exchange.log", "report.html"])
def test_passing_test_exchange_is_logged(probe_session, which):
    text = probe_session[0] if which == "exchange.log" else probe_session[1]
    for pattern in _expected_lines("STATUS", "STATUS OFF"):
        assert re.search(pattern, text), f"{pattern!r} not found in {which}"


@pytest.mark.parametrize("which", ["exchange.log", "report.html"])
def test_failing_test_exchange_is_logged(probe_session, which):
    text = probe_session[0] if which == "exchange.log" else probe_session[1]
    for pattern in _expected_lines("on", "ERR UNKNOWN_CMD"):
        assert re.search(pattern, text), f"{pattern!r} not found in {which}"


def test_exchange_log_has_one_section_per_test(probe_session):
    log = probe_session[0]
    assert "===== test_probe.py::test_probe_passes [passed] =====" in log
    assert "===== test_probe.py::test_probe_fails [failed] =====" in log
    # Each section holds only its own test's exchange (RESET between tests).
    passes, fails = log.split("===== test_probe.py::test_probe_fails")
    assert '"on"' not in passes and '"STATUS"' not in fails
