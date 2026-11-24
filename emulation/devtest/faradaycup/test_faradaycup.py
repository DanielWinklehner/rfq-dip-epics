"""Faraday cup Opta FC1 as the lab has it (reference/lab-2026): two values on a libcom1 protocol 1
board. Read, plant input, silent/close and recovery, and that the IOC sends the board nothing but
the query A (no identity, no acknowledged set: a protocol 1 board answers them ERR0)."""
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

SIM = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
INVALID = 3
PVS = ["FC1:data", "FC1:i1:getcurrent", "FC1:i2:getcurrent"]
GONE = ["FC:current:get", "FC:data", "FC:id", "FC1:id", "FC1:firmware", "FC1:channels"]

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
        c.release("i1")


def log_lines(name):
    with open(os.path.join(BUILD, name)) as handle:
        return [l.rstrip() for l in handle if not l.lstrip().startswith("#")]


def test_startup_log_is_clean():
    lines = log_lines("ioc.log")
    assert any("iocRun: All initialization complete" in l for l in lines)
    assert [l for l in lines if ERROR.search(l) and not l.startswith("on error ")] == []


def test_every_pv_is_valid():
    wait_for("FC1:i1:getcurrent", lambda v, s: s == 0)
    for name in PVS:
        assert read(name)[1] == 0, name
    assert read("FC1:i1:getcurrent")[0] == pytest.approx(1e-6, rel=0.05)
    assert read("FC1:i2:getcurrent")[0] == 0.0
    assert list(read("FC1:data")[0]) == pytest.approx([read("FC1:i1:getcurrent")[0], 0.0], rel=0.05)


def test_unit_is_not_claimed():
    """What i1 and i2 are and their unit is not known (the sketch was not found)."""
    for name in ("FC1:i1:getcurrent", "FC1:i2:getcurrent"):
        assert epics.caget(name + ".EGU") == "", name


def test_the_assumed_names_are_gone():
    for name in GONE:
        assert not epics.PV(name).wait_for_connection(timeout=1.0), name


def test_plant_drives_i1(ctl):
    ctl.set("i1", 2.5e-7)
    wait_for("FC1:i1:getcurrent", lambda v, s: v == pytest.approx(2.5e-7, rel=0.05) and s == 0)
    assert read("FC1:i2:getcurrent") == (0.0, 0)


@pytest.mark.parametrize("mode", ["silent", "close"])
def test_fault_and_recovery(ctl, mode):
    ctl.fault(mode)
    t0 = time.time()
    for name in PVS:
        wait_for(name, lambda v, s: s == INVALID, timeout=5.0)
    print("%s: INVALID after %.1f s" % (mode, time.time() - t0))
    ctl.clear()
    for name in PVS:
        wait_for(name, lambda v, s: s == 0, timeout=30.0)


def test_only_the_query_all_reaches_the_board():
    """The board as flashed speaks protocol 1: the IOC must send it nothing but A. The simulator
    counts the requests by their first character and logs every command a protocol 1 board would
    answer with ERR0."""
    with ControlClient(SIM, 6000) as c:
        heads = c.stats()["heads"]
    print("requests by first character: %s" % heads)
    assert set(heads) == {"A"} and heads["A"] > 10, heads
    assert [l for l in log_lines("sim.log") if "answered ERR0" in l] == []


def test_log_has_only_communication_messages():
    bad = [l for l in log_lines("ioc.log")
           if ERROR.search(l) and not l.startswith("on error ") and not COMMUNICATION.search(l)]
    assert bad == []
