"""MKS G-series MFC: set point and flow, wink, NAK and missing answers, two units on one bus."""
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

SIM = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
INVALID = 3
LAB, BUS = 6000, 6001          # control ports of mfc_lab and mfc_bus
RECORDS = ["getSP", "setSP", "getWink", "setWink", "getFlow"]
READS = ["getSP", "getWink", "getFlow"]

ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
# Expected while faults are injected: a device that does not answer, or answers NAK
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


@pytest.fixture
def lab():
    with ControlClient(SIM, LAB) as c:
        yield c
        c.clear()


@pytest.fixture
def bus():
    with ControlClient(SIM, BUS) as c:
        yield c
        c.clear()


def log_lines():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        return [l.rstrip() for l in handle if not l.lstrip().startswith("#")]


def test_startup_log_is_clean():
    lines = log_lines()
    assert any("iocRun: All initialization complete" in l for l in lines)
    assert [l for l in lines if ERROR.search(l) and not l.startswith("on error ")] == []


def test_every_pv_is_valid():
    for prefix in ("MFC", "MFCA", "MFCB"):
        wait_for(prefix + ":getFlow", lambda v, s: s == 0)
        for rec in RECORDS:
            wait_for("%s:%s" % (prefix, rec), lambda v, s: s == 0, timeout=3.0)
    assert read("MFC:setSP")[0] == pytest.approx(-20.0)    # @init: the device's initial -20 %
    assert read("MFC:getFlow")[0] == pytest.approx(0.0, abs=0.1)


def test_set_point_read_back_and_flow(lab):
    assert put("MFC:setSP", 40.0) == 0
    wait_for("MFC:getSP", lambda v, s: v == pytest.approx(40.0) and s == 0, timeout=3.0)
    assert lab.get("254.setpoint")["value"] == pytest.approx(40.0)
    wait_for("MFC:getFlow", lambda v, s: v == pytest.approx(20.0, abs=0.2) and s == 0)  # 40 % of 50 sccm
    assert put("MFC:setSP", -20.0) == 0
    wait_for("MFC:getFlow", lambda v, s: v == pytest.approx(0.0, abs=0.2))


def test_wink():
    assert put("MFC:setWink", 1) == 0
    wait_for("MFC:getWink", lambda v, s: v == 1 and s == 0, timeout=3.0)
    assert put("MFC:setWink", 0) == 0
    wait_for("MFC:getWink", lambda v, s: v == 0 and s == 0, timeout=3.0)


def test_nak_ends_in_an_alarm(lab):
    lab.fault("trip")                                  # the unit answers NAK98 to everything
    assert put("MFC:setSP", 10.0) == INVALID
    assert put("MFC:setWink", 1) == INVALID
    wait_for("MFC:getSP", lambda v, s: s == INVALID, timeout=5.0)
    lab.clear()
    assert put("MFC:setSP", 10.0) == 0
    assert put("MFC:setWink", 0) == 0
    assert lab.get("254.setpoint")["value"] == pytest.approx(10.0)


@pytest.mark.parametrize("mode", ["silent", "close"])
def test_no_answer_ends_in_an_alarm_and_recovers(lab, mode):
    before = lab.get("254.setpoint")["value"]
    lab.fault(mode)
    assert put("MFC:setSP", before + 5.0) == INVALID
    for rec in READS:
        wait_for("MFC:" + rec, lambda v, s: s == INVALID, timeout=5.0)
    assert lab.get("254.setpoint")["value"] == before         # a silent unit executes nothing
    lab.clear()
    for rec in READS:
        wait_for("MFC:" + rec, lambda v, s: s == 0, timeout=30.0)
    assert put("MFC:setSP", before + 5.0) == 0
    for prefix in ("MFCA", "MFCB"):                    # the other line did not notice
        assert read(prefix + ":getSP")[1] == 0


def test_second_address_does_not_disturb_the_first(bus):
    assert put("MFCA:setSP", 30.0) == 0
    assert put("MFCB:setSP", 60.0) == 0
    wait_for("MFCA:getFlow", lambda v, s: v == pytest.approx(30.0, abs=0.3) and s == 0)   # FS 100
    wait_for("MFCB:getFlow", lambda v, s: v == pytest.approx(120.0, abs=0.5) and s == 0)  # FS 200
    assert bus.get("1.setpoint")["value"] == pytest.approx(30.0)
    assert bus.get("2.setpoint")["value"] == pytest.approx(60.0)
    bus.fault("silent", unit=2)
    wait_for("MFCB:getSP", lambda v, s: s == INVALID, timeout=5.0)
    assert put("MFCB:setSP", 70.0) == INVALID
    assert put("MFCA:setSP", 35.0) == 0
    for _ in range(10):                                # unit 1 stays healthy meanwhile
        for rec in READS:
            assert read("MFCA:" + rec)[1] == 0
        time.sleep(0.3)
    wait_for("MFCA:getSP", lambda v, s: v == pytest.approx(35.0), timeout=3.0)
    bus.clear()
    for rec in READS:
        wait_for("MFCB:" + rec, lambda v, s: s == 0, timeout=10.0)
    assert bus.get("2.setpoint")["value"] == pytest.approx(60.0)


def test_log_has_only_communication_messages():
    bad = [l for l in log_lines()
           if ERROR.search(l) and not l.startswith("on error ") and not COMMUNICATION.search(l)]
    assert bad == []
