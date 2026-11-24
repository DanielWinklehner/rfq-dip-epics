"""The dipole supply records (EPICS/Db/dipole.db) against the DAQ service daq/mist2daq with its sim
backend, through one real IOC.

The service is the case's simulator (sim.cmd, run_service.sh). Its read-only status port (6000)
gives what the IOC cannot: the voltage written to the (simulated) NI box and the commands
received. The tests run in the order of this file and build on each other.
"""
import json
import math
import os
import re
import socket
import time

import epics
import pytest

SIM = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
NO_ALARM, MINOR, MAJOR, INVALID = 0, 1, 2, 3
UDF_STATUS = 17                     # menuAlarmStat: UDF

PER_VOLT = 10.0                     # daq.yaml: A per V, output and monitor
TAU = 1.0                           # daq.yaml: lag of the simulated monitor, s
READ_PVS = ["dipole:data", "dipole:current:held", "dipole:current:get",
            "dipole:id", "dipole:firmware", "dipole:channels",
            "wide:data", "wide:current:held", "wide:current:get"]
# The time within which every read record is INVALID after the service stops: the identity
# records are read every 10 s (libcom1_device.db), plus the reply timeouts queued on the port.
SILENT_INVALID_S = 15.0

_PVS = {}


def pv(name):
    if name not in _PVS:
        _PVS[name] = epics.PV(name, auto_monitor=False)
        _PVS[name].wait_for_connection(timeout=5)
    return _PVS[name]


def read(name, as_string=False):
    d = pv(name).get_with_metadata(use_monitor=False, form="time", as_string=as_string, timeout=3)
    assert d is not None, "%s does not answer" % name
    return d


def put(name, value):
    assert pv(name).put(value, wait=True, timeout=10) == 1, "put to %s did not complete" % name


def wait_until(what, test, timeout, period=0.1):
    end = time.time() + timeout
    while True:
        last = test()
        if last is True:
            return
        if time.time() > end:
            pytest.fail("%s: not reached within %g s, last %r" % (what, timeout, last))
        time.sleep(period)


def status():
    with socket.create_connection((SIM, 6000), timeout=3) as s:
        s.sendall(b'{"cmd": "status"}\n')
        line = s.makefile().readline()
    reply = json.loads(line)
    assert reply["ok"], reply
    return reply["status"]


def sets_received(st=None):
    c = (st or status())["counts"]["commands"]
    return c.get("S", 0) + c.get("s", 0)


def severities(names):
    return {n: read(n)["severity"] for n in names}


def all_valid(names):
    bad = {n: s for n, s in severities(names).items() if s != NO_ALARM}
    return True if not bad else bad


def service(state):
    with open(os.path.join(BUILD, "daq-run"), "w") as f:
        f.write(state + "\n")


def restart_ioc():
    path = os.path.join(BUILD, "ioc-restart")
    with open(path) as f:
        n = len(f.read())
    with open(path, "w") as f:
        f.write("x" * (n + 1))


def log_lines(name="ioc.log"):
    with open(os.path.join(BUILD, name)) as handle:
        return [l.rstrip() for l in handle if not l.lstrip().startswith("#")]


ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad |parse|link", re.I)


# --- at the start -------------------------------------------------------------------------------

def test_startup_log_is_clean():
    lines = log_lines()
    assert any("iocRun: All initialization complete" in l for l in lines)
    assert [l for l in lines if ERROR.search(l) and not l.startswith("on error ")] == []


def test_identity_records_valid():
    wait_until("identity valid", lambda: all_valid(["dipole:id", "dipole:firmware", "dipole:channels"]), 15)
    assert read("dipole:id", as_string=True)["value"] == "DipoleDAQ"
    assert read("dipole:firmware", as_string=True)["value"] == "mist2daq-0.1"
    assert epics.caget("dipole:channels.VAL$", as_string=True, timeout=3) == "o1,i1"


def test_nothing_written_and_set_value_not_known_at_the_start():
    st = status()
    assert st["sim"]["writes"] == 0, st
    assert st["channels"]["o1"]["held"] is None
    assert st["channels"]["o1"]["volts_written"] is None
    assert sets_received(st) == 0
    wait_until("read-back valid", lambda: all_valid(["dipole:data", "dipole:current:get"]), 10)
    held = read("dipole:current:held")
    assert math.isnan(held["value"]) and held["severity"] == INVALID and held["status"] == UDF_STATUS, held
    sp = read("dipole:current:set")
    assert sp["severity"] == INVALID and sp["status"] == UDF_STATUS, sp   # not 0 A as if known
    assert read("dipole:current:get")["value"] == pytest.approx(0.0, abs=1e-6)


# --- a set and its read-back ----------------------------------------------------------------------

def test_set_acknowledged_scaled_and_followed_with_lag():
    target = 25.0
    t0 = time.time()
    put("dipole:current:set", target)
    sp = read("dipole:current:set")
    assert sp["severity"] == NO_ALARM, sp
    st = status()
    assert st["channels"]["o1"]["volts_written"] == pytest.approx(target / PER_VOLT)
    assert st["sim"]["outputs_v"]["Dev1/ao0"] == pytest.approx(target / PER_VOLT)
    assert st["channels"]["o1"]["held"] == pytest.approx(target)
    # the read-back: every new sample against the first-order lag at the sample's own time stamp
    samples, last_stamp = [], None
    while time.time() < t0 + 6 * TAU:
        d = read("dipole:current:get")
        if d["timestamp"] != last_stamp:
            last_stamp = d["timestamp"]
            samples.append((d["timestamp"] - t0, d["value"], d["severity"]))
        time.sleep(0.05)
    print("read-back after the set (s, A):", ["%.2f:%.2f" % s[:2] for s in samples])
    early = [v for t, v, _ in samples if 0.05 < t < 0.6 * TAU]
    assert early and all(v < 0.6 * target for v in early), "no lag: %r" % samples
    for t, v, sev in samples:
        if t > 0.05:
            model = target * (1 - math.exp(-t / TAU))
            assert v == pytest.approx(model, abs=0.08 * target), (t, v, model)
            assert sev == NO_ALARM
    assert samples[-1][1] == pytest.approx(target, rel=0.01)
    wait_until("held = set", lambda: read("dipole:current:held")["value"] == pytest.approx(target) or
               read("dipole:current:held"), 3)
    assert read("dipole:current:held")["severity"] == NO_ALARM


def test_set_beyond_drive_limit_is_clamped_by_the_record():
    put("dipole:current:set", 95.0)                    # DRVH 80
    sp = read("dipole:current:set")
    assert sp["value"] == pytest.approx(80.0) and sp["severity"] == NO_ALARM, sp
    assert status()["channels"]["o1"]["volts_written"] == pytest.approx(8.0)


def test_set_beyond_service_limit_is_refused():
    before = status()
    put("wide:current:set", 120.0)                     # record allows 150, the service 100
    sp = read("wide:current:set")
    assert sp["severity"] == INVALID, sp               # ERR5 instead of ok
    after = status()
    assert after["counts"]["sets_refused_limit"] == before["counts"]["sets_refused_limit"] + 1
    assert after["sim"]["outputs_v"]["Dev1/ao0"] == pytest.approx(8.0)   # unchanged
    assert after["sim"]["writes"] == before["sim"]["writes"]
    assert after["channels"]["o1"]["held"] == pytest.approx(80.0)
    put("wide:current:set", -10.0)                     # below the service's 0 A
    assert read("wide:current:set")["severity"] == INVALID
    assert status()["sim"]["outputs_v"]["Dev1/ao0"] == pytest.approx(8.0)


def test_readback_update_rate():
    stamps, end = set(), time.time() + 10.0
    while time.time() < end:
        stamps.add(read("dipole:current:get")["timestamp"])
        time.sleep(0.05)
    s = sorted(stamps)
    rate = (len(s) - 1) / (s[-1] - s[0])
    print("read-back: %d updates in %.2f s = %.2f per s" % (len(s) - 1, s[-1] - s[0], rate))
    assert 1.8 <= rate <= 2.2                           # SCAN .5 second


# --- a second client ------------------------------------------------------------------------------

def test_second_client_is_refused_while_the_ioc_is_connected():
    before = status()
    with socket.create_connection((SIM, 5000), timeout=3) as s:
        s.settimeout(3)
        try:
            s.sendall(b"I\n")
        except OSError:
            pass
        try:
            data = s.recv(100)
        except ConnectionResetError:
            data = b""
    assert data == b"", "the second client got %r" % data   # closed at once, no reply
    after = status()
    assert after["clients"]["refused"] == before["clients"]["refused"] + 1
    assert after["clients"]["replaced"] == before["clients"]["replaced"]
    time.sleep(1.0)
    assert all_valid(["dipole:data", "dipole:current:get", "dipole:current:held"]) is True


# --- IOC restart: nothing written, the set record shows what the service holds ---------------------

def test_ioc_restart_writes_nothing_and_takes_over():
    before = status()
    held = before["channels"]["o1"]["held"]
    restart_ioc()
    time.sleep(1.0)
    _PVS.clear()
    wait_until("IOC back", lambda: epics.caget("DEVTEST:heartbeat", timeout=1) is not None, 60, 0.5)
    _PVS.clear()
    wait_until("set record taken over", lambda: read("dipole:current:set")["severity"] == NO_ALARM or
               read("dipole:current:set"), 15)
    assert read("dipole:current:set")["value"] == pytest.approx(held)
    time.sleep(2.0)
    after = status()
    assert sets_received(after) == sets_received(before), (before["counts"], after["counts"])
    assert after["sim"]["writes"] == before["sim"]["writes"]
    assert after["channels"]["o1"]["held"] == pytest.approx(held)


# --- the service stopped and started -----------------------------------------------------------------

def test_service_stopped_every_record_invalid_then_valid_with_set_value_not_known():
    wait_until("all valid before", lambda: all_valid(READ_PVS[:6]), 15)
    t0 = time.time()
    service("stop")
    try:
        def every_invalid():
            sev = severities(READ_PVS)
            return True if all(s == INVALID for s in sev.values()) else sev
        wait_until("every read record INVALID", every_invalid, SILENT_INVALID_S + 5, 0.2)
        took = time.time() - t0
        print("service stopped: every read record INVALID after %.1f s" % took)
        assert took <= SILENT_INVALID_S
    finally:
        service("run")
    t1 = time.time()
    wait_until("valid again", lambda: all_valid(["dipole:data", "dipole:current:get", "dipole:id",
                                                 "dipole:firmware", "dipole:channels"]), 30, 0.2)
    print("service started: valid again after %.1f s" % (time.time() - t1))
    held = read("dipole:current:held")
    assert math.isnan(held["value"]) and held["severity"] == INVALID and held["status"] == UDF_STATUS, held
    st = status()
    assert st["channels"]["o1"]["held"] is None and st["sim"]["writes"] == 0
    # the set record is not processed by the polls: it keeps its last value (see dipole.db)
    print("dipole:current:set after the service restart:", read("dipole:current:set"))
    put("dipole:current:set", 10.0)
    assert read("dipole:current:set")["severity"] == NO_ALARM
    wait_until("held known again", lambda: read("dipole:current:held")["severity"] == NO_ALARM or
               read("dipole:current:held"), 3)
    assert status()["channels"]["o1"]["volts_written"] == pytest.approx(1.0)


# --- logs -------------------------------------------------------------------------------------------

RUNTIME = re.compile(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.\d+ ")
FAULT_MESSAGE = re.compile(
    r"^\S+ \S+ (?:DIPOLE (?:\S+: )?(?:No reply within \d+ ms|Input \"|mismatch after \d+ bytes|got \""
    r"|device \S+ 0 disconnected|No match for \"|connectCallback\(\w+\) called unexpectedly"
    r"|Device sent \"ERR5\"|.*ERR5)"
    r"|(?:cbLow|scan-[0-9.]+|CAS-\S+) \S+ lockRequest: (?:port \S+ not connected|status returned to normal))")


def test_ioc_log_has_no_database_protocol_or_link_error():
    lines = log_lines()
    bad = [l for l in lines if not l.startswith("on error ") and (ERROR.search(l) or RUNTIME.match(l))
           and not FAULT_MESSAGE.match(l)]
    print("\n".join(l for l in lines if RUNTIME.match(l)))
    assert bad == []


def test_service_log():
    lines = log_lines("sim.log")
    assert any("no output written at the start" in l for l in lines)
    assert any("refused" in l and "outside limits" in l for l in lines)
    assert any("stopping (SIGTERM)" in l for l in lines)
    assert not any("Traceback" in l for l in lines)
