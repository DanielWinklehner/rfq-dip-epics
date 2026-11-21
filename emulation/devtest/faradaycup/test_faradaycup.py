"""Faraday cup Opta (placeholder libcom1 device): read, plant input, silent/close and recovery."""
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

SIM = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
INVALID = 3
PVS = ["FC:current:get", "FC:data", "FC:id", "FC:firmware", "FC:channels"]

# Lines of the IOC log that mean a database, protocol or link error. Messages about a device
# that does not answer are expected here (the faults are injected on purpose).
ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
COMMUNICATION = re.compile(r": No reply within \d+ ms|: Input \".*\" mismatch|: device \S+ \d+ disconnected")


def read(name):
    """(value, severity), read fresh from the IOC."""
    pv = epics.get_pv(name, form="time")
    value = pv.get(use_monitor=False, timeout=2.0)
    assert value is not None, "%s did not answer" % name
    return value, pv.severity


def wait_for(name, test, timeout=6.0):
    end = time.time() + timeout
    while True:
        value, sevr = read(name)
        if test(value, sevr):
            return value, sevr
        if time.time() > end:
            pytest.fail("%s: no luck within %g s, last %r severity %d" % (name, timeout, value, sevr))
        time.sleep(0.2)


@pytest.fixture
def ctl():
    with ControlClient(SIM, 6000) as c:
        yield c
        c.clear()
        c.release("c1")


def log_lines():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        return [l.rstrip() for l in handle if not l.lstrip().startswith("#")]


def test_startup_log_is_clean():
    lines = log_lines()
    assert any("iocRun: All initialization complete" in l for l in lines)
    assert [l for l in lines if ERROR.search(l) and not l.startswith("on error ")] == []


def test_every_pv_is_valid():
    wait_for("FC:current:get", lambda v, s: s == 0)
    for name in PVS:
        assert read(name)[1] == 0, name
    assert read("FC:id")[0] == "FaradayCupOpta"
    assert read("FC:channels")[0] == "c1"
    assert read("FC:current:get")[0] == pytest.approx(1e-6, rel=0.05)


def test_plant_drives_the_current(ctl):
    ctl.set("c1", 2.5e-7)
    wait_for("FC:current:get", lambda v, s: v == pytest.approx(2.5e-7, rel=0.05) and s == 0)


@pytest.mark.parametrize("mode", ["silent", "close"])
def test_fault_and_recovery(ctl, mode):
    ctl.fault(mode)
    t0 = time.time()
    wait_for("FC:current:get", lambda v, s: s == INVALID, timeout=5.0)
    wait_for("FC:data", lambda v, s: s == INVALID, timeout=5.0)
    print("%s: INVALID after %.1f s" % (mode, time.time() - t0))
    ctl.clear()
    wait_for("FC:current:get", lambda v, s: s == 0, timeout=30.0)
    wait_for("FC:id", lambda v, s: s == 0, timeout=15.0)


def test_log_has_only_communication_messages():
    bad = [l for l in log_lines()
           if ERROR.search(l) and not l.startswith("on error ") and not COMMUNICATION.search(l)]
    assert bad == []
