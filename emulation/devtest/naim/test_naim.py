"""Edwards nAIM: aim.db and aim.proto in a real IOC against the edwards_naim simulator."""

import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

BUILD = os.environ["DEVTEST_BUILD"]
SIM = os.environ["SIM_HOST"]
PRESSURE, ENABLE = "AIM:getpressure", "AIM:enable"
INVALID = 3


@pytest.fixture(scope="module")
def ctl():
    with ControlClient(SIM, 6002) as c:
        yield c


def get(name):
    return epics.caget(name, use_monitor=False, timeout=2.0)


def sevr(name):
    return epics.caget(name + ".SEVR", use_monitor=False, timeout=2.0)


def stat(name):
    return epics.caget(name + ".STAT", as_string=True, use_monitor=False, timeout=2.0)


def put(name, value):
    assert epics.caput(name, value, wait=True, timeout=10.0) == 1


def wait_for(what, test, timeout=10.0):
    end = time.time() + timeout
    while True:
        value = what()
        if test(value):
            return value
        if time.time() > end:
            pytest.fail("timeout after %g s, last value %r" % (timeout, value))
        time.sleep(0.1)


def valid():
    return wait_for(lambda: sevr(PRESSURE), lambda s: s == 0, 15)


def test_pressure_is_read_and_valid():
    valid()
    assert 1e-7 < get(PRESSURE) < 1e-5
    assert epics.PV(PRESSURE).get_ctrlvars(timeout=2)["units"] == "torr"


def test_pressure_follows_the_plant(ctl):
    ctl.set("pressure", 3.0e-7)
    try:
        wait_for(lambda: get(PRESSURE), lambda p: abs(p / 3.0e-7 - 1) < 0.05)
    finally:
        ctl.release("pressure")


def test_enable_switches_the_gauge_and_off_is_invalid(ctl):
    put(ENABLE, 0)
    assert sevr(ENABLE) == 0
    assert ctl.get("on")["value"] == 0.0
    wait_for(lambda: sevr(PRESSURE), lambda s: s == INVALID, 5)
    assert stat(PRESSURE) == "CALC"
    put(ENABLE, 1)
    assert sevr(ENABLE) == 0
    wait_for(lambda: sevr(PRESSURE), lambda s: s == 0, 10)   # after striking
    assert 1e-7 < get(PRESSURE) < 1e-5


def test_gauge_error_bit_is_invalid(ctl):
    ctl.set("error", 1)
    try:
        wait_for(lambda: sevr(PRESSURE), lambda s: s == INVALID, 5)
    finally:
        ctl.release("error")
    valid()


def test_rejected_enable_ends_in_alarm(ctl):
    ctl.set("reject", 5)                         # "*C752 5": invalid in current state
    try:
        put(ENABLE, 0)
        assert sevr(ENABLE) == INVALID
        assert ctl.get("on")["value"] == 1.0
    finally:
        ctl.release("reject")
    put(ENABLE, 1)
    assert sevr(ENABLE) == 0


def test_unanswered_enable_ends_in_alarm(ctl):
    ctl.fault("silent")
    try:
        put(ENABLE, 1)
        assert sevr(ENABLE) == INVALID
        assert stat(ENABLE) == "TIMEOUT"
    finally:
        ctl.clear("silent")
    put(ENABLE, 1)
    assert sevr(ENABLE) == 0


@pytest.mark.parametrize("mode", ["silent", "close", "garbage"])
def test_fault_and_recovery(ctl, mode):
    valid()
    before = get(PRESSURE)
    ctl.fault(mode)
    try:
        t0 = time.time()
        wait_for(lambda: sevr(PRESSURE), lambda s: s == INVALID, 5)
        print("%s: INVALID after %.1f s" % (mode, time.time() - t0))
        if mode == "garbage":
            for _ in range(10):
                assert abs(get(PRESSURE) / before - 1) < 0.2    # no wrong value
                time.sleep(0.2)
    finally:
        ctl.clear(mode)
    t0 = time.time()
    wait_for(lambda: sevr(PRESSURE), lambda s: s == 0, 40)
    print("%s cleared: valid after %.1f s" % (mode, time.time() - t0))


def test_poll_rate(ctl):
    ctl.stats(reset=True)
    time.sleep(5.0)
    s = ctl.stats()
    rate = s["requests"] / s["elapsed_s"]
    print("nAIM poll rate %.2f Hz, line busy %.1f %%" % (rate, 100 * s["busy_s"] / s["elapsed_s"]))
    assert rate == pytest.approx(1.0, rel=0.2)


ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
EXPECTED = re.compile(r"No reply|does not match|mismatch|Timeout|timed out|connect|Connection"
                      r"|disconnect|Broken pipe|reset by peer|still busy|asynManager"
                      r"|additional errors of the following type", re.I)


def test_ioc_log_has_no_database_protocol_or_link_error():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    done = [i for i, l in enumerate(lines) if "iocRun: All initialization complete" in l]
    assert done, "IOC did not finish iocInit"
    init, run = lines[:done[0]], lines[done[0]:]
    assert [l for l in init if ERROR.search(l) and not l.startswith("on error ")] == []
    assert [l for l in run if ERROR.search(l) and not EXPECTED.search(l)] == []
    # a gauge that is off or in error is not a protocol error: no message for it
    assert [l for l in run if "getpressure" in l and "V752 " in l and "does not match" in l] == []
