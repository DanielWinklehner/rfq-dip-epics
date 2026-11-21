"""The five libcom1 Arduino boards against their simulators and one real IOC.

Prefixes, ports and channel orders as in the lab (DEVICE=THM, VALVE, PRESSURE, SENSOR, INTLK).
The tests run in the order of this file: reading, sets, thermocouple faults, door switches,
communication faults per board, identity, and last the IOC log.
"""
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

SIM_HOST = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]

NO_ALARM, MINOR, MAJOR, INVALID = 0, 1, 2, 3
FIRMWARE = "Nov 21 2026"   # placeholder for __DATE__, as in sim.yaml


def _board(prefix, port, identity, channels, values):
    return dict(prefix=prefix, port=port, identity=identity, channels=channels,
                values=["%s:%s" % (prefix, v) for v in values] + ["%s:data" % prefix])


BOARDS = {
    "gauges": _board("PRESSURE", 5006, "IonGaugeController", "p1,p2",
                     ["apg:getpressure", "diag_box:getpressure"]),
    "sensorbox": _board("SENSOR", 5010, "SensorBox",
                        "t1,t2,t3,t4,t5,t6,t7,f1,f2,f3,f4,f5",
                        ["t%d:gettemp" % n for n in range(1, 8)] +
                        ["f%d:getflow" % n for n in range(1, 6)]),
    "interlockbox": _board("INTLK", 5011, "InterlockBox", "i1,i2,s1,s2",
                           ["i1:get_interlock", "i2:get_interlock"]),
    "valvebox": _board("VALVE", 5012, "SolenoidValveBox", "s1,s2,s3,s4,s5,s6,s7,s8",
                       ["s%d:get" % n for n in range(1, 9)]),
    "thermocouple": _board("THM", 5020, "Thermocouple",
                           "t1,t2,t3,t4,j1,j2,j3,j4,f1,f2,f3,f4,a1,a2,a3,a4",
                           ["t%d:get" % n for n in range(1, 5)] +
                           ["j%d:get" % n for n in range(1, 5)] +
                           ["f%d:get" % n for n in range(1, 5)]),
}
BOARDS["interlockbox"]["values"].append("interlock_open")   # no prefix, as in the lab

# simulator signal -> PV holding it, for comparing values (tolerance covers noise and lag)
VALUE_MAP = (
    [("gauges", "p1", "PRESSURE:apg:getpressure"), ("gauges", "p2", "PRESSURE:diag_box:getpressure")] +
    [("sensorbox", "t%d" % n, "SENSOR:t%d:gettemp" % n) for n in range(1, 8)] +
    [("sensorbox", "f%d" % n, "SENSOR:f%d:getflow" % n) for n in range(1, 6)] +
    [("interlockbox", "i%d" % n, "INTLK:i%d:get_interlock" % n) for n in (1, 2)] +
    [("valvebox", "s%d" % n, "VALVE:s%d:get" % n) for n in range(1, 9)] +
    [("thermocouple", "%s%d" % (c, n), "THM:%s%d:get" % (c, n)) for c in "tjf" for n in range(1, 5)]
)

_PVS = {}


def pv(name):
    if name not in _PVS:
        _PVS[name] = epics.PV(name, auto_monitor=False)
        _PVS[name].wait_for_connection(timeout=5)
    return _PVS[name]


def read(name, as_string=False):
    """dict with value, severity, status, timestamp (fresh read, no monitor)."""
    d = pv(name).get_with_metadata(use_monitor=False, form="time", as_string=as_string, timeout=3)
    assert d is not None, "%s does not answer" % name
    return d


def severity(name):
    return read(name)["severity"]


def put(name, value):
    assert pv(name).put(value, wait=True, timeout=10) == 1, "put to %s did not complete" % name


def wait_until(what, test, timeout):
    end = time.time() + timeout
    last = None
    while True:
        last = test()
        if last is True:
            return
        if time.time() > end:
            pytest.fail("%s: not reached within %g s, last %r" % (what, timeout, last))
        time.sleep(0.2)


def control(board):
    return ControlClient(SIM_HOST, BOARDS[board]["port"] + 1000)


def sim_value(board, signal):
    """True value of a simulator signal (no noise)."""
    with control(board) as c:
        return c.get(signal)["value"]


def wait_value(name, expected, timeout=5):
    def test():
        value = read(name)["value"]
        return True if value == expected else value
    wait_until("%s == %r" % (name, expected), test, timeout)


def all_severities(names):
    return {n: severity(n) for n in names}


def none_in_alarm(names):
    sev = all_severities(names)
    bad = {n: s for n, s in sev.items() if s != NO_ALARM}
    return True if not bad else bad


# --- normal operation --------------------------------------------------------------------------

@pytest.mark.parametrize("board", list(BOARDS))
def test_every_pv_read_and_not_in_alarm(board):
    names = BOARDS[board]["values"]
    wait_until("%s PVs without alarm" % board, lambda: none_in_alarm(names), 15)
    stamps = {n: read(n)["timestamp"] for n in names}
    time.sleep(1.5)
    stale = [n for n in names if read(n)["timestamp"] <= stamps[n]]
    assert stale == [], "not updating: %s" % stale


@pytest.mark.parametrize("board,signal,name", VALUE_MAP)
def test_value_matches_simulator(board, signal, name):
    expected = sim_value(board, signal)
    tol = max(0.5, abs(expected) * 0.05)
    value = read(name)["value"]
    assert value == pytest.approx(expected, abs=tol), "%s = %r, simulator %s = %r" % (
        name, value, signal, expected)


def test_units_and_precision():
    for name in ["THM:t1:get", "THM:j4:get", "SENSOR:t7:gettemp"]:
        assert pv(name).get_ctrlvars()["units"] == "degC", name
    for name in ["PRESSURE:apg:getpressure", "PRESSURE:diag_box:getpressure"]:
        assert pv(name).get_ctrlvars()["units"] == "Torr", name
    assert pv("SENSOR:f1:getflow").get_ctrlvars()["units"] == ""   # unit not known


# --- valve sets --------------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, 9))
def test_valve_set_and_readback(n):
    for value in (1, 0):
        put("VALVE:s%d:set" % n, value)
        wait_value("VALVE:s%d:get" % n, value)
        assert sim_value("valvebox", "s%d" % n) == value
        assert severity("VALVE:s%d:set" % n) == NO_ALARM
        assert severity("VALVE:s%d:get" % n) == NO_ALARM


def test_rejected_set_alarms():
    put("DEVTEST:reject:set", 1)
    d = read("DEVTEST:reject:set")
    assert d["severity"] == INVALID, d
    # the box is fine otherwise
    assert none_in_alarm(BOARDS["valvebox"]["values"]) is True


def test_unanswered_set_alarms():
    with control("valvebox") as c:
        c.fault("silent")
    try:
        put("VALVE:s1:set", 1)
        assert severity("VALVE:s1:set") == INVALID
        assert sim_value("valvebox", "s1") == 0.0        # a silent box does not execute
    finally:
        with control("valvebox") as c:
            c.clear()
    wait_until("valve box recovers", lambda: none_in_alarm(BOARDS["valvebox"]["values"]), 10)
    put("VALVE:s1:set", 0)
    assert severity("VALVE:s1:set") == NO_ALARM
    assert read("VALVE:s1:get")["value"] == 0


# --- thermocouple faults -----------------------------------------------------------------------

# check_fault(): code -> error value of readThermocouple() (MAX31856.h) and the state name
FAULTS = [(3, 10000.0, "Open thermocouple"), (2, 10001.0, "Voltage fault"), (1, 10002.0, "No sensor chip")]


@pytest.mark.parametrize("n,code,error_value,state", [(i + 1,) + f for i, f in enumerate(FAULTS)])
def test_thermocouple_fault(n, code, error_value, state):
    t, f = "THM:t%d:get" % n, "THM:f%d:get" % n
    with control("thermocouple") as c:
        # as the firmware does it: the temperature channel carries the error value and the
        # fault channel the code
        c.set("t%d" % n, error_value)
        c.set("f%d" % n, code)
    try:
        wait_value(f, code)
        assert read(f, as_string=True)["value"] == state
        assert severity(f) == MAJOR
        assert severity(t) == INVALID
        others = [x for x in BOARDS["thermocouple"]["values"] if x not in (t, f)]
        assert none_in_alarm(others) is True
    finally:
        with control("thermocouple") as c:
            c.release("t%d" % n)
            c.release("f%d" % n)
    wait_until("%s recovers" % t, lambda: none_in_alarm([t, f]), 5)
    assert read(f, as_string=True)["value"] == "No fault"


def test_sensorbox_thermocouple_fault():
    with control("sensorbox") as c:
        c.set("t3", 10000.0)
    try:
        wait_until("SENSOR:t3:gettemp INVALID", lambda: severity("SENSOR:t3:gettemp") == INVALID, 5)
        assert severity("SENSOR:t2:gettemp") == NO_ALARM
    finally:
        with control("sensorbox") as c:
            c.release("t3")
    wait_until("SENSOR:t3:gettemp recovers", lambda: severity("SENSOR:t3:gettemp") == NO_ALARM, 5)


# --- door switches -----------------------------------------------------------------------------

@pytest.mark.parametrize("i1,i2", [(1, 1), (0, 1), (1, 0), (0, 0)])
def test_door_switches(i1, i2):
    """Firmware: an input reads 1 (HIGH) when its door is closed; both closed = interlock closed."""
    with control("interlockbox") as c:
        c.set("i1", i1)
        c.set("i2", i2)
    try:
        expected_open = 0 if (i1 and i2) else 1
        wait_value("INTLK:i1:get_interlock", i1)
        wait_value("INTLK:i2:get_interlock", i2)
        wait_value("interlock_open", expected_open)
        assert severity("interlock_open") == (MAJOR if expected_open else NO_ALARM)
        for n, v in ((1, i1), (2, i2)):
            name = "INTLK:i%d:get_interlock" % n
            assert read(name, as_string=True)["value"] == ("Closed" if v else "Open")
            assert severity(name) == (NO_ALARM if v else MAJOR)
    finally:
        with control("interlockbox") as c:
            c.release("i1")
            c.release("i2")
    wait_until("doors closed again", lambda: none_in_alarm(BOARDS["interlockbox"]["values"]), 5)
    assert read("interlock_open")["value"] == 0


# --- communication faults, one board at a time -------------------------------------------------

@pytest.mark.parametrize("mode", ["silent", "close", "garbage"])
@pytest.mark.parametrize("board", list(BOARDS))
def test_fault_isolated_and_recovers(board, mode):
    mine = BOARDS[board]["values"]
    others = [n for b in BOARDS if b != board for n in BOARDS[b]["values"]]
    wait_until("all PVs without alarm before the fault", lambda: none_in_alarm(mine + others), 15)
    stamps = {n: read(n)["timestamp"] for n in others if n.endswith(":data")}
    started = time.time()
    with control(board) as c:
        c.fault(mode)
    try:
        # garbage: a reply that does not parse is INVALID too (StreamDevice input mismatch)
        def all_invalid():
            sev = all_severities(mine)
            return True if all(s == INVALID for s in sev.values()) else sev
        wait_until("%s PVs INVALID after %s" % (board, mode), all_invalid, 5)
        assert time.time() - started <= 5.5
        time.sleep(1.0)
        assert none_in_alarm(others) is True
        stale = [n for n in stamps if read(n)["timestamp"] <= stamps[n]]
        assert stale == [], "other boards stopped updating: %s" % stale
    finally:
        with control(board) as c:
            c.clear()
    wait_until("%s recovers after %s" % (board, mode), lambda: none_in_alarm(mine), 15)


# --- identity ----------------------------------------------------------------------------------

@pytest.mark.parametrize("board", list(BOARDS))
def test_identity(board):
    b = BOARDS[board]
    p = b["prefix"]
    # read 10 s after a fault at most: wait for the next identity scan
    wait_until("%s identity without alarm" % board,
               lambda: none_in_alarm(["%s:id" % p, "%s:firmware" % p, "%s:channels" % p]), 15)
    assert read("%s:id" % p, as_string=True)["value"] == b["identity"]
    assert read("%s:firmware" % p, as_string=True)["value"] == FIRMWARE
    # :channels is an lsi: the full list is VAL$ (char array), VAL itself is cut at 39
    # characters for plain string clients (the thermocouple board's list has 47)
    assert epics.caget("%s:channels.VAL$" % p, as_string=True, timeout=3) == b["channels"]
    assert read("%s:channels" % p, as_string=True)["value"] == b["channels"][:39]


def test_channels_invalid_when_silent():
    """The identity records still turn INVALID when the board stops answering (10 s scan)."""
    with control("thermocouple") as c:
        c.fault("silent")
    try:
        # up to 10 s until the next identity scan, then three queries of 1 s timeout each,
        # queued behind the timing-out polls of :data
        wait_until("THM:channels INVALID", lambda: severity("THM:channels") == INVALID or
                   severity("THM:channels"), 25)
        assert pv("THM:channels").get_ctrlvars() is not None
    finally:
        with control("thermocouple") as c:
            c.clear()
    wait_until("THM:channels recovers", lambda: severity("THM:channels") == NO_ALARM, 15)
    assert epics.caget("THM:channels.VAL$", as_string=True, timeout=3) == BOARDS["thermocouple"]["channels"]


# --- IOC log -----------------------------------------------------------------------------------

# Database, protocol and link errors (dbLoadRecords, StreamDevice protocol parsing, CA links)
CONFIG_ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                          r"|syntax|bad |parse|link", re.I)
# A timestamped message of StreamDevice or asyn
RUNTIME = re.compile(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.\d+ ")
# The only run-time messages allowed: what the deliberate faults of this test produce on the
# five ports (no reply, a garbled or rejected reply, a dropped or refused connection)
FAULT_MESSAGE = re.compile(
    r"^\S+ \S+ (?:(?:AVR6|AVR10|AVR11|AVR12|thermo) (?:\S+: )?"
    r"(?:No reply within \d+ ms|Input \"|mismatch after \d+ bytes|got \"|device \S+ 0 disconnected"
    r"|No match for \"|connectCallback\(\w+\) called unexpectedly)"
    r"|(?:cbLow|scan-[0-9.]+) \S+ lockRequest: (?:port \S+ not connected|status returned to normal))")


def test_ioc_log_has_no_database_protocol_or_link_error():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    assert any("iocRun: All initialization complete" in l for l in lines)
    errors = [l for l in lines if not l.startswith("on error ") and
              (CONFIG_ERROR.search(l) or RUNTIME.match(l)) and not FAULT_MESSAGE.match(l)]
    assert errors == []
