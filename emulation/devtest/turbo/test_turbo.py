"""Two NT 20 turbopumps: the Opta (relays and contacts) and the listen-only monitor ports."""
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

SIM = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
MAJOR, INVALID = 2, 3
OPTA, NT20 = 6000, {1: 6001, 2: 6002}       # control ports
STOPPED, ACCELERATING, NORMAL, FAILURE, INCONSISTENT = range(5)
RELAY_PVS = ["start:get", "atspeed:get", "accel:get", "failure:get", "state:get"]
MONITOR_PVS = ["raw:get", "speed:get", "current:get"]
RATED = 1200.0

ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
COMMUNICATION = re.compile(r": No reply within \d+ ms|: Input \".*\" mismatch|: device \S+ \d+ disconnected")


def read(name):
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


def put(name, value):
    assert epics.caput(name, value, wait=True, timeout=5.0) == 1
    return read(name)[1]


class Recorder:
    """Every value a PV posts, to show that no transient state appears."""

    def __init__(self, name):
        self.values = []
        self.pv = epics.PV(name, callback=lambda value=None, **kw: self.values.append(value))
        self.pv.wait_for_connection(2.0)

    def stop(self):
        self.pv.clear_callbacks()
        self.pv.disconnect()
        return self.values


@pytest.fixture
def opta():
    with ControlClient(SIM, OPTA) as c:
        yield c
        c.clear()


@pytest.fixture
def pumps():
    with ControlClient(SIM, NT20[1]) as one, ControlClient(SIM, NT20[2]) as two:
        yield {1: one, 2: two}
        for p in (1, 2):
            put("TURBO%d:start:set" % p, 0)
        one.clear()
        two.clear()


def stopped(p):
    put("TURBO%d:start:set" % p, 0)
    wait_for("TURBO%d:state:get" % p, lambda v, s: v == STOPPED and s == 0)


def log_lines():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        return [l.rstrip() for l in handle if not l.lstrip().startswith("#")]


def test_startup_log_is_clean():
    lines = log_lines()
    assert any("iocRun: All initialization complete" in l for l in lines)
    assert [l for l in lines if ERROR.search(l) and not l.startswith("on error ")] == []


def test_every_pv_is_valid():
    for p in (1, 2):
        put("TURBO%d:start:set" % p, 0)               # a set record is UDF until written
        for rec in RELAY_PVS + MONITOR_PVS + ["start:set", "age:get"]:
            wait_for("TURBO%d:%s" % (p, rec), lambda v, s: s == 0, timeout=10.0)
        assert read("TURBO%d:state:get" % p)[0] == STOPPED
        assert read("TURBO%d:raw:get" % p)[0].startswith("NT20 f=")
    for rec in ("data", "id", "firmware", "channels"):
        assert read("TURBO:" + rec)[1] == 0
    assert read("TURBO:id")[0] == "TurboOpta"
    assert read("TURBO:channels")[0] == "r1,r2,r3,r4,n1,a1,f1,n2,a2,f2"


def test_start_accelerate_normal_stop(pumps):
    state = Recorder("TURBO1:state:get")
    assert put("TURBO1:start:set", 1) == 0
    wait_for("TURBO1:start:get", lambda v, s: v == 1 and s == 0, timeout=2.0)
    wait_for("TURBO1:state:get", lambda v, s: v == ACCELERATING and s == 0, timeout=3.0)
    assert read("TURBO1:accel:get")[0] == 1
    wait_for("TURBO1:speed:get", lambda v, s: 0 < v < RATED and s == 0, timeout=10.0)
    wait_for("TURBO1:current:get", lambda v, s: v > 2.0 and s == 0, timeout=10.0)
    wait_for("TURBO1:state:get", lambda v, s: v == NORMAL and s == 0, timeout=20.0)
    assert read("TURBO1:atspeed:get")[0] == 1 and read("TURBO1:accel:get")[0] == 0
    wait_for("TURBO1:speed:get", lambda v, s: v == pytest.approx(RATED, abs=1), timeout=10.0)
    wait_for("TURBO1:current:get", lambda v, s: v == pytest.approx(0.6, abs=0.1), timeout=10.0)
    assert read("TURBO1:age:get")[0] <= 9
    assert read("TURBO2:state:get")[0] == STOPPED     # pump 2 did not move
    stopped(1)
    wait_for("TURBO1:speed:get", lambda v, s: v < RATED - 100, timeout=10.0)
    time.sleep(1.0)
    values = state.stop()
    assert INCONSISTENT not in values and FAILURE not in values, values


def test_trip_gives_failure_and_stop_resets_it(pumps):
    assert put("TURBO1:start:set", 1) == 0
    wait_for("TURBO1:state:get", lambda v, s: v == ACCELERATING, timeout=3.0)
    pumps[1].fault("trip")
    wait_for("TURBO1:failure:get", lambda v, s: v == 1 and s == MAJOR, timeout=2.0)
    wait_for("TURBO1:state:get", lambda v, s: v == FAILURE and s == MAJOR, timeout=2.0)
    time.sleep(2.0)
    assert read("TURBO1:failure:get")[0] == 1         # latched while run is still on
    stopped(1)                                         # STOP resets the failure
    assert read("TURBO1:failure:get") == (0, 0)
    assert pumps[1].info() and pumps[1].get()["faults"] == []


def test_pump_2_is_independent(pumps):
    stopped(1)
    assert put("TURBO2:start:set", 1) == 0
    wait_for("TURBO2:state:get", lambda v, s: v == ACCELERATING, timeout=3.0)
    pumps[2].fault("trip")
    wait_for("TURBO2:state:get", lambda v, s: v == FAILURE, timeout=2.0)
    for rec in RELAY_PVS:
        assert read("TURBO1:" + rec)[1] == 0
    assert read("TURBO1:state:get")[0] == STOPPED
    stopped(2)


def test_unacknowledged_start_and_silent_opta(opta, pumps):
    stopped(1)
    opta.fault("silent")
    assert put("TURBO1:start:set", 1) == INVALID      # not confirmed
    for p in (1, 2):
        for rec in RELAY_PVS:
            wait_for("TURBO%d:%s" % (p, rec), lambda v, s: s == INVALID, timeout=5.0)
    for p in (1, 2):                                   # the monitor ports do not care
        for rec in MONITOR_PVS + ["age:get"]:
            assert read("TURBO%d:%s" % (p, rec))[1] == 0
    assert opta.get("r1")["value"] == 0                # a silent Opta executes nothing
    opta.clear()
    for rec in RELAY_PVS:
        wait_for("TURBO1:" + rec, lambda v, s: s == 0, timeout=5.0)
    assert read("TURBO1:state:get")[0] == STOPPED


def test_closed_opta_recovers(opta, pumps):
    opta.fault("close")
    for rec in RELAY_PVS:
        wait_for("TURBO1:" + rec, lambda v, s: s == INVALID, timeout=5.0)
    opta.clear()
    for rec in RELAY_PVS:
        wait_for("TURBO1:" + rec, lambda v, s: s == 0, timeout=30.0)
    wait_for("TURBO:id", lambda v, s: s == 0, timeout=15.0)


def test_monitor_silent_and_closed(pumps):
    """Pump 1's monitor goes silent, pump 2's closes its port, at the same time."""
    pumps[1].fault("silent")
    pumps[2].fault("close")
    t0 = time.time()
    for p in (1, 2):
        wait_for("TURBO%d:age:get" % p, lambda v, s: v > 20 and s == MAJOR, timeout=30.0)
        for rec in MONITOR_PVS:
            wait_for("TURBO%d:%s" % (p, rec), lambda v, s: s == INVALID, timeout=3.0)
        for rec in RELAY_PVS:                          # the Opta still works
            assert read("TURBO%d:%s" % (p, rec))[1] == 0
    print("monitor PVs INVALID after %.0f s" % (time.time() - t0))
    assert put("TURBO1:start:set", 1) == 0             # and the pump still runs
    wait_for("TURBO1:state:get", lambda v, s: v == ACCELERATING, timeout=3.0)
    stopped(1)
    pumps[1].clear()
    pumps[2].clear()
    for p in (1, 2):
        wait_for("TURBO%d:age:get" % p, lambda v, s: v < 10 and s == 0, timeout=40.0)
        for rec in MONITOR_PVS:
            wait_for("TURBO%d:%s" % (p, rec), lambda v, s: s == 0, timeout=3.0)


def test_record_that_does_not_parse(pumps):
    """Records arrive but do not parse: speed and current INVALID, raw shows the line, age low."""
    pumps[1].fault("garbage")
    raw, _ = wait_for("TURBO1:raw:get", lambda v, s: v and not v.startswith("NT20 f="), timeout=12.0)
    t0 = time.time()
    for rec in ("speed:get", "current:get"):
        wait_for("TURBO1:" + rec, lambda v, s: s == INVALID, timeout=3.0)
    print("speed and current INVALID %.1f s after the first garbled record %r" % (time.time() - t0, raw))
    assert read("TURBO1:raw:get")[1] == 0
    assert read("TURBO1:age:get")[1] == 0 and read("TURBO1:age:get")[0] < 10
    wait_for("TURBO1:age:get", lambda v, s: v < 3, timeout=10.0)    # a second garbled record
    assert read("TURBO1:speed:get")[1] == INVALID                     # still not trusted
    for rec in MONITOR_PVS:                                           # pump 2 is not affected
        assert read("TURBO2:" + rec)[1] == 0
    pumps[1].clear()
    wait_for("TURBO1:raw:get", lambda v, s: v.startswith("NT20 f=") and s == 0, timeout=12.0)
    for rec in ("speed:get", "current:get", "age:get"):
        wait_for("TURBO1:" + rec, lambda v, s: s == 0, timeout=2.0)


def test_log_has_only_communication_messages():
    bad = [l for l in log_lines()
           if ERROR.search(l) and not l.startswith("on error ") and not COMMUNICATION.search(l)]
    assert bad == []
