"""INFICON VGC401: vgc401.db and vgc401.proto in a real IOC against the inficon_vgc401 simulator.

The simulator's true pressure is in torr; it reports it in its unit, with the mantissa rounded
to two decimals as the manual says (p. 60): 1 % is the tolerance.
"""

import json
import math
import os
import re
import subprocess
import sys
import time

import epics
import pytest

from mist2sim.control import ControlClient

BUILD = os.environ["DEVTEST_BUILD"]
SIM = os.environ["SIM_HOST"]
P = "FORELINE:"
PRESSURE, STATE, UNIT = P + "getpressure", P + "getstate", P + "getunit"
GAUGE, ERROR_WORD, VERSION = P + "getgauge", P + "geterror", P + "getversion"
NO_ALARM, MINOR, MAJOR, INVALID = 0, 1, 2, 3
TRUE_TORR = 0.03


@pytest.fixture(scope="module")
def ctl():
    with ControlClient(SIM, 6034) as c:
        yield c


def get(name, **kw):
    return epics.caget(name, use_monitor=False, timeout=2.0, **kw)


def sevr(name):
    return get(name + ".SEVR")


# Samples of one PV, taken by a NEW process: a list of (value, severity), each pair from ONE
# Channel Access reply (two gets can straddle a change). A new process has a new channel, which
# searches at once and often; a channel of this process from before an IOC restart found the
# new IOC only after seconds (seen: not connected for 6 s, also after PV.disconnect()).
SAMPLER = """
import json, sys, time, epics
pv = epics.PV(sys.argv[1], form="time", auto_monitor=False)
end, out = time.time() + float(sys.argv[2]), []
while time.time() < end:
    data = pv.get_with_metadata(use_monitor=False, timeout=0.5) if pv.wait_for_connection(timeout=0.5) else None
    if data is not None and data.get("value") is not None:
        out.append((data["value"], data["severity"]))
    time.sleep(0.1)
print(json.dumps(out))
"""


def samples(name, seconds):
    done = subprocess.run([sys.executable, "-c", SAMPLER, name, str(seconds)], capture_output=True, text=True,
                          timeout=seconds + 30)
    assert done.returncode == 0, done.stderr
    return [tuple(pair) for pair in json.loads(done.stdout.strip().splitlines()[-1])]


def wait_for(what, test, timeout=10.0):
    end = time.time() + timeout
    while True:
        value = what()
        if value is not None and test(value):
            return value
        if time.time() > end:
            pytest.fail("timeout after %g s, last value %r" % (timeout, value))
        time.sleep(0.1)


def near(value, truth, rel=0.01):
    return value is not None and math.isfinite(value) and abs(value / truth - 1) < rel


def valid():
    wait_for(lambda: sevr(PRESSURE), lambda s: s == NO_ALARM, 15)
    wait_for(lambda: get(PRESSURE), lambda p: near(p, TRUE_TORR), 5)


def restart_ioc_trigger():
    path = os.path.join(BUILD, "ioc-restart")
    with open(path) as f:
        n = len(f.read())
    with open(path, "w") as f:
        f.write("x" * (n + 1))


def restart_ioc():
    """Restart the IOC and come back when this process sees the new one. Its channels from
    before the restart find the new IOC only at their next search, which can be seconds away
    (seen: None for more than 6 s), so wait for the ones the tests read right after."""
    restart_ioc_trigger()
    time.sleep(1.0)                 # the old IOC is stopped within 0.2 s
    wait_for(lambda: get("DEVTEST:heartbeat"), lambda h: h < 30, 60)
    for name in (PRESSURE + ".SEVR", P + "_pr1.SEVR", PRESSURE, UNIT):
        wait_for(lambda: epics.get_pv(name).wait_for_connection(timeout=1.0), lambda ok: ok, 60)


# --- read correctly -----------------------------------------------------------------------------

def test_first_readings():
    valid()
    assert get(STATE, as_string=True) == "Measurement data okay"
    assert sevr(STATE) == NO_ALARM
    assert epics.PV(PRESSURE).get_ctrlvars(timeout=2)["units"] == "torr"
    assert get(UNIT, as_string=True) == "mbar"
    # the records of the 2 s scan follow the pressure: an exchange takes 0.2 s on the real controller
    wait_for(lambda: get(GAUGE), lambda g: g == "PSG", 5)
    wait_for(lambda: get(VERSION), lambda v: v == "302-519-E", 5)
    wait_for(lambda: get(ERROR_WORD, as_string=True), lambda e: e == "No error", 5)
    assert sevr(ERROR_WORD) == NO_ALARM


@pytest.mark.parametrize("unit,name", [(0, "mbar"), (1, "Torr"), (2, "Pascal"), (3, "Micron")])
def test_pressure_in_torr_for_each_unit(ctl, unit, name):
    ctl.set("unit", unit)
    try:
        wait_for(lambda: get(UNIT, as_string=True), lambda u: u == name, 5)
        time.sleep(1.2)                         # one more pressure after the unit
        p = wait_for(lambda: get(PRESSURE), lambda p: near(p, TRUE_TORR), 5)
        assert sevr(PRESSURE) == NO_ALARM
        print("unit %s: %s = %.4g torr" % (name, PRESSURE, p))
    finally:
        ctl.release("unit")
    valid()


def test_pressure_follows_the_controller(ctl):
    ctl.set("pressure", 2.0e-3)
    try:
        wait_for(lambda: get(PRESSURE), lambda p: near(p, 2.0e-3), 5)
    finally:
        ctl.release("pressure")
    valid()


def test_unknown_unit_is_invalid(ctl):
    valid()
    ctl.set("unit", 7)
    try:
        wait_for(lambda: sevr(UNIT), lambda s: s == INVALID, 5)
        wait_for(lambda: sevr(PRESSURE), lambda s: s == INVALID, 3)
        assert math.isnan(get(PRESSURE))
    finally:
        ctl.release("unit")
    valid()


# --- the status digit (p. 60) and the line ------------------------------------------------------

STATES = [(1, "Underrange", MINOR), (2, "Overrange", MINOR), (3, "Sensor error", INVALID),
          (4, "Sensor off", INVALID), (5, "No sensor", INVALID),
          (6, "Identification error", INVALID), (7, "Error BAG, BPG, HPG, BCG", INVALID)]


@pytest.mark.parametrize("status,word,severity", STATES)
def test_status_digit(ctl, status, word, severity):
    valid()
    ctl.set("status", status)
    try:
        wait_for(lambda: get(STATE, as_string=True), lambda s: s == word, 5)
        assert sevr(STATE) == severity
        wait_for(lambda: sevr(PRESSURE), lambda s: s == severity, 3)
        p = get(PRESSURE)
        if severity == MINOR:
            assert near(p, TRUE_TORR)           # the value as sent
        else:
            assert math.isnan(p)                # never a stale or a zero value
        print("status %d: %s, severity %d, pressure %r" % (status, word, severity, p))
    finally:
        ctl.release("status")
    valid()


def test_gauge_identification_follows_no_sensor(ctl):
    ctl.set("status", 5)
    try:
        wait_for(lambda: get(GAUGE), lambda g: g == "noSEn", 5)
    finally:
        ctl.release("status")
    wait_for(lambda: get(GAUGE), lambda g: g == "PSG", 5)


def test_controller_error_word(ctl):
    ctl.set("controller_error", 1)
    try:
        wait_for(lambda: get(ERROR_WORD, as_string=True), lambda e: e == "Controller error", 5)
        assert sevr(ERROR_WORD) == MAJOR
    finally:
        ctl.release("controller_error")
    wait_for(lambda: get(ERROR_WORD, as_string=True), lambda e: e == "No error", 5)


@pytest.mark.parametrize("mode,word", [("silent", "No reply"), ("garbage", "Bad reply or disconnected"),
                                       ("close", "Bad reply or disconnected")])
def test_line_fault_and_recovery(ctl, mode, word):
    valid()
    ctl.fault(mode)
    try:
        t0 = time.time()
        wait_for(lambda: sevr(PRESSURE), lambda s: s == INVALID, 5)
        print("%s: INVALID after %.1f s" % (mode, time.time() - t0))
        for _ in range(10):
            assert math.isnan(get(PRESSURE))
            time.sleep(0.2)
        assert get(STATE, as_string=True) == word
        assert sevr(STATE) == INVALID
    finally:
        ctl.clear(mode)
    t0 = time.time()
    valid()
    print("%s cleared: valid after %.1f s" % (mode, time.time() - t0))


# --- the IOC's start ----------------------------------------------------------------------------

def sim_log():
    with open(os.path.join(BUILD, "sim.log")) as handle:
        return [l.rstrip() for l in handle]


def log_time(line):
    """Seconds of the day of a line of the simulator's log ("2026-11-25 09:23:06,437 ...")."""
    h, m, s = line.split()[1].replace(",", ".").split(":")
    return 3600 * int(h) + 60 * int(m) + float(s)


def test_controller_that_sends_by_itself_at_the_start(ctl):
    """The IOC starts and connects (st.cmd); the controller is switched off and on at that
    moment, so it sends every 100 ms (sim.yaml) into the new IOC before the IOC's first
    request. Every value the IOC then shows is right, and its first character ends the
    automatic output (p. 55)."""
    valid()
    connected = len([l for l in sim_log() if "client (" in l and " connected" in l])
    restart_ioc_trigger()
    wait_for(lambda: len([l for l in sim_log() if "client (" in l and " connected" in l]),
             lambda n: n > connected, 30)
    ctl.set("power", 0)
    ctl.set("power", 1)
    ctl.release("power")
    seen = samples(PRESSURE, 8.0)
    log = sim_log()
    power_on = [log_time(l) for l in log if "power on" in l][-1]
    stopped = [log_time(l) for l in log if "first character received" in l][-1]
    lines_before = int((stopped - power_on) / 0.1)
    assert ctl.get("continuous")["value"] == 0.0          # the IOC's first character ended it
    good = [(v, s) for v, s in seen if s != INVALID]
    assert good, seen
    assert all(near(v, TRUE_TORR) for v, s in good), seen
    assert lines_before >= 3                              # the IOC did get the automatic output
    print("controller on %.2f s before the IOC's first character: about %d lines sent by "
          "itself; then %d samples, %d valid, all within 1 %% of %g torr" % (
              stopped - power_on, lines_before, len(seen), len(good), TRUE_TORR))


def test_pressure_invalid_until_the_unit_was_read(ctl):
    """The controller refuses UNI from before the IOC starts: PR1 is read, the pressure
    stays INVALID; the first UNI reply makes it valid."""
    ctl.set("refuse_uni", 1)
    try:
        restart_ioc()
        wait_for(lambda: sevr(P + "_pr1"), lambda s: s == NO_ALARM, 15)
        for _ in range(15):
            assert sevr(PRESSURE) == INVALID
            assert math.isnan(get(PRESSURE))
            time.sleep(0.2)
    finally:
        ctl.release("refuse_uni")
    valid()


# --- read only, and the load on the line --------------------------------------------------------

def test_nothing_sent_that_sets_a_parameter(ctl):
    ctl.stats(reset=True)
    time.sleep(6.0)
    s = ctl.stats()
    assert set(s["heads"]) <= {"P", "U", "T", "E", "\x05"}, s["heads"]
    assert ctl.get("n_set")["value"] == 0.0             # since the simulator started
    rate = s["requests"] / s["elapsed_s"]
    print("requests %d in %.1f s (%.2f /s), heads %s, line busy %.1f %%" % (
        s["requests"], s["elapsed_s"], rate, s["heads"], 100 * s["busy_s"] / s["elapsed_s"]))
    # every second PR1 and <ENQ>, every 2 s UNI, TID, ERR, PNR and an <ENQ> each: 6 per second
    assert rate == pytest.approx(6.0, rel=0.15)


ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
EXPECTED = re.compile(r"No reply|does not match|mismatch|Timeout|timed out|connect|Connection"
                      r"|disconnect|Broken pipe|reset by peer|still busy|asynManager|restarted"
                      r"|additional errors of the following type|input \"|was expected"
                      r"|status returned to normal", re.I)


def test_ioc_log_has_no_database_protocol_or_link_error():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    done = [i for i, l in enumerate(lines) if "iocRun: All initialization complete" in l]
    assert done, "IOC did not finish iocInit"
    init = lines[:done[0]]
    assert [l for l in init if ERROR.search(l) and not l.startswith("on error ")] == []
    run = lines[done[0]:]
    assert [l for l in run if ERROR.search(l) and not EXPECTED.search(l)
            and not l.startswith("on error ")] == []
