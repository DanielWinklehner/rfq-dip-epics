"""TDK GENESYS: tdk.db and tdk.proto in a real IOC against the tdk_genesys simulator.

The tests run in file order and leave the supply as they found it (output off) where they can.
"""

import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

BUILD = os.environ["DEVTEST_BUILD"]
SIM = os.environ["SIM_HOST"]
P = "TDK:"
READS = ["voltage:read", "current:read", "power:get", "status:get", "mode:get", "fault:get"]
SETS = ["voltage:setpoint", "current:setpoint", "status:setpoint"]
INVALID = 3


@pytest.fixture(scope="module")
def ctl():
    with ControlClient(SIM, 6001) as c:
        yield c


def get(name):
    return epics.caget(P + name, use_monitor=False, timeout=2.0)


def sevr(name):
    return epics.caget(P + name + ".SEVR", use_monitor=False, timeout=2.0)


def put(name, value):
    assert epics.caput(P + name, value, wait=True, timeout=10.0) == 1


def wait_for(what, test, timeout=10.0):
    end = time.time() + timeout
    while True:
        value = what()
        if test(value):
            return value
        if time.time() > end:
            pytest.fail("timeout after %g s, last value %r" % (timeout, value))
        time.sleep(0.1)


def all_valid(names):
    return wait_for(lambda: {n: sevr(n) for n in names}, lambda s: INVALID not in s.values(), 15)


def all_invalid(names, timeout=5.0):
    return wait_for(lambda: {n: sevr(n) for n in names}, lambda s: set(s.values()) == {INVALID},
                    timeout)


def output(volts, amps, on):
    put("voltage:setpoint", volts)
    put("current:setpoint", amps)
    put("status:setpoint", on)


def test_every_pv_is_read_and_valid():
    all_valid(READS)
    for name in READS + SETS:
        assert get(name) is not None, name
        assert sevr(name) != INVALID, name
    assert get("fault:get") == 0
    assert get("mode:get") == 0                              # OFF


def test_constant_voltage():
    output(2.0, 300.0, 1)
    wait_for(lambda: get("voltage:read"), lambda v: abs(v - 2.0) < 0.02)
    wait_for(lambda: get("current:read"), lambda i: abs(i - 80.0) < 0.5)   # 2 V / 25 mOhm
    assert epics.caget(P + "mode:get", as_string=True, use_monitor=False) == "CV"
    assert get("status:get") == 1
    assert get("power:get") == pytest.approx(160.0, abs=3.0)
    assert [sevr(n) for n in SETS] == [0, 0, 0]


def test_constant_current():
    output(8.0, 100.0, 1)
    wait_for(lambda: get("current:read"), lambda i: abs(i - 100.0) < 0.5)
    wait_for(lambda: get("voltage:read"), lambda v: abs(v - 2.5) < 0.02)  # 100 A x 25 mOhm
    wait_for(lambda: epics.caget(P + "mode:get", as_string=True, use_monitor=False),
             lambda m: m == "CC")
    assert get("power:get") == pytest.approx(250.0, abs=4.0)


def test_output_switch():
    put("status:setpoint", 0)
    wait_for(lambda: get("status:get"), lambda s: s == 0)
    wait_for(lambda: get("current:read"), lambda i: i < 0.5)
    wait_for(lambda: get("mode:get"), lambda m: m == 0)   # polled once a second, on its own
    put("status:setpoint", 1)
    wait_for(lambda: get("status:get"), lambda s: s == 1)
    put("status:setpoint", 0)


def test_set_with_error_reply_ends_in_alarm(ctl):
    output(2.0, 100.0, 0)
    # The drive limits keep the IOC inside the rating: widen them to make the supply refuse.
    # DRVH is a pp field: writing it processes the record, so restore it after a valid value.
    epics.caput(P + "voltage:setpoint.DRVH", 9.0, wait=True)
    epics.caput(P + "current:setpoint.DRVH", 400.0, wait=True)
    try:
        put("voltage:setpoint", 8.6)                         # above 105 % of 8 V: E01
        assert sevr("voltage:setpoint") == INVALID
        put("current:setpoint", 350.0)                       # above 105 % of 300 A: C05
        assert sevr("current:setpoint") == INVALID
        sim = ctl.get()["signals"]
        assert (sim["pv"]["value"], sim["pc"]["value"]) == (2.0, 100.0)   # refused
    finally:
        output(2.0, 100.0, 0)
        epics.caput(P + "voltage:setpoint.DRVH", 8.0, wait=True)
        epics.caput(P + "current:setpoint.DRVH", 300.0, wait=True)
    ctl.set("enable_open", 1)                                # rear panel interlock open
    try:
        put("status:setpoint", 1)                            # E07
        assert sevr("status:setpoint") == INVALID
    finally:
        ctl.release("enable_open")
    sim = ctl.get()["signals"]
    assert (sim["pv"]["value"], sim["pc"]["value"], sim["output"]["value"]) == (2.0, 100.0, 0.0)
    output(2.0, 100.0, 0)                                    # accepted again
    assert [sevr(n) for n in SETS] == [0, 0, 0]


def test_set_without_reply_ends_in_alarm(ctl):
    ctl.fault("silent")
    try:
        for name, value in zip(SETS, (1.0, 50.0, 0)):
            put(name, value)
            assert sevr(name) == INVALID, name
            assert epics.caget(P + name + ".STAT", as_string=True, use_monitor=False) == "TIMEOUT"
    finally:
        ctl.clear("silent")
    output(2.0, 100.0, 0)
    assert [sevr(n) for n in SETS] == [0, 0, 0]


def test_silent_and_recovery(ctl):
    ctl.fault("silent")
    t0 = time.time()
    all_invalid(READS)
    print("silent: all read PVs INVALID after %.1f s" % (time.time() - t0))
    ctl.clear("silent")
    t0 = time.time()
    all_valid(READS)
    print("silent cleared: all valid after %.1f s" % (time.time() - t0))


def test_close_and_reopen(ctl):
    ctl.fault("close")
    t0 = time.time()
    all_invalid(READS)
    print("close: all read PVs INVALID after %.1f s" % (time.time() - t0))
    ctl.clear("close")
    t0 = time.time()
    wait_for(lambda: {n: sevr(n) for n in READS}, lambda s: INVALID not in s.values(), 40)
    print("reopened: all valid after %.1f s" % (time.time() - t0))
    output(2.0, 100.0, 0)


def test_garbage_gives_alarms_and_no_wrong_values(ctl):
    output(2.0, 300.0, 1)
    wait_for(lambda: get("voltage:read"), lambda v: abs(v - 2.0) < 0.02)
    wait_for(lambda: (get("status:get"), get("mode:get")), lambda s: s == (1, 1))
    ctl.fault("garbage")
    try:
        all_invalid(READS)
        end = time.time() + 2.0
        while time.time() < end:
            assert abs(get("voltage:read") - 2.0) < 0.02
            assert abs(get("current:read") - 80.0) < 0.5
            assert (get("status:get"), get("mode:get"), get("fault:get")) == (1, 1, 0)
            time.sleep(0.1)
    finally:
        ctl.clear("garbage")
    all_valid(READS)
    put("status:setpoint", 0)


def test_trip_and_recovery(ctl):
    output(2.0, 300.0, 1)
    wait_for(lambda: get("status:get"), lambda s: s == 1)
    ctl.fault("trip")                                        # OVP shutdown
    ctl.clear("trip")                                        # the supply keeps it latched
    wait_for(lambda: get("fault:get"), lambda f: f == 0x10)
    assert sevr("fault:get") == 2                            # MAJOR
    assert (get("status:get"), get("mode:get")) == (0, 0)
    wait_for(lambda: get("current:read"), lambda i: i < 0.5)
    put("status:setpoint", 1)                                # OUT 1 resets the OVP circuit
    wait_for(lambda: get("fault:get"), lambda f: f == 0)
    wait_for(lambda: get("current:read"), lambda i: abs(i - 80.0) < 0.5)
    assert sevr("fault:get") == 0
    put("status:setpoint", 0)


def test_power_cycle_recovers_within_15_s(ctl):
    output(2.0, 300.0, 1)
    ctl.set("ac_power", 0)
    all_invalid(READS)
    ctl.release("ac_power")                                  # back on, unaddressed
    t0 = time.time()
    all_valid(READS)
    took = time.time() - t0
    print("power cycle: all read PVs valid %.1f s after power on" % took)
    assert took < 15.0
    assert get("status:get") == 0                            # safe start: output off
    assert ctl.get("pv")["value"] == 2.0                     # last settings kept
    output(2.0, 300.0, 1)
    wait_for(lambda: get("current:read"), lambda i: abs(i - 80.0) < 0.5)
    put("status:setpoint", 0)


def test_update_rate_against_line_arithmetic(ctl):
    output(2.0, 300.0, 1)
    wait_for(lambda: get("current:read"), lambda i: abs(i - 80.0) < 0.5)
    info = ctl.info()["settings"]
    baud, bits, turn = info["baud"], info["bits_per_char"], info["turnaround_ms"] / 1000.0
    # characters per transaction, terminators included
    fast = [len("MV?\r") + len("2.000\r"), len("MC?\r") + len("080.00\r")]
    slow = [len("OUT?\r") + len("ON\r"), len("MODE?\r") + len("CV\r"), len("FLT?\r") + len("00\r")]
    t_fast = sum(n * bits / baud + turn for n in fast)
    t_slow = sum(n * bits / baud + turn for n in slow)
    line_limit = (1.0 - t_slow) / t_fast                     # Hz, if the line were the limit
    predicted = min(10.0, line_limit)                        # SCAN .1 second

    count = {"n": 0}
    # current:read: with 0.05 A noise at 0.01 A resolution nearly every update is a new value
    pv = epics.PV(P + "current:read", auto_monitor=True)
    pv.add_callback(lambda **kw: count.__setitem__("n", count["n"] + 1))
    pv.wait_for_connection(5)
    ctl.stats(reset=True)
    time.sleep(1.0)
    count["n"] = 0
    t0 = time.time()
    time.sleep(10.0)
    measured = count["n"] / (time.time() - t0)
    stats = ctl.stats()
    pv.clear_callbacks()
    per_pv = (stats["requests"] / stats["elapsed_s"] - 3.0) / 2.0
    print("rate at %d baud, %d bits/char, %.0f ms turnaround: line busy %.1f ms per fast cycle, "
          "line limit %.0f Hz, predicted %.1f Hz, measured %.2f Hz (CA), %.2f Hz (simulator), "
          "line busy %.0f %%" % (baud, bits, turn * 1000, t_fast * 1000, line_limit, predicted,
                                  measured, per_pv, 100 * stats["busy_s"] / stats["elapsed_s"]))
    assert measured == pytest.approx(predicted, rel=0.1)
    assert per_pv == pytest.approx(predicted, rel=0.1)
    put("status:setpoint", 0)


# Lines that mean an error (as in devtest/example). After iocInit, the tests above cause
# communication messages on purpose (no reply, mismatching replies, a dropped connection):
# those are allowed after initialisation, nothing else is.
ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
EXPECTED = re.compile(r"No reply from device|does not match|mismatch|Timeout|timed out"
                      r"|connect|Connection|disconnect|Broken pipe|reset by peer|still busy"
                      r"|Device not connected|asynManager"
                      r"|additional errors of the following type", re.I)


def test_ioc_log_has_no_database_protocol_or_link_error():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    done = [i for i, l in enumerate(lines) if "iocRun: All initialization complete" in l]
    assert done, "IOC did not finish iocInit"
    init, run = lines[:done[0]], lines[done[0]:]
    assert [l for l in init if ERROR.search(l) and not l.startswith("on error ")] == []
    assert [l for l in run if ERROR.search(l) and not EXPECTED.search(l)] == []
