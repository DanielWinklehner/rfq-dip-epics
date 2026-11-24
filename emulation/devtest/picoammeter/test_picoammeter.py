"""Keithley 6485 picoammeter: picoammeter.db and keithley6485.proto in a real IOC against the
keithley_6485 simulator (task T25). The tests run in this order; the first one needs the
simulator as it starts: in its power-on state."""

import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

BUILD = os.environ["DEVTEST_BUILD"]
SIM = os.environ["SIM_HOST"]
P = "pico1:"
INVALID = 3
RANGES = [2e-9, 2e-8, 2e-7, 2e-6, 2e-5, 2e-4, 2e-3, 2e-2]      # range:set states 1..8
PUBLIC = ["current:get", "range:set", "range:get", "zcheck:set", "zcheck:get", "nplc:get",
          "idn:get"]
READBACKS = ["current:get", "range:get", "zcheck:get", "nplc:get"]
SCAN_S = 1.0                     # picoammeter.db default
REPLY_TIMEOUT_S = 0.5            # keithley6485.proto
SET_HEADS = re.compile(r"setting: ")    # the simulator logs every executed setting command


@pytest.fixture(scope="module")
def ctl():
    with ControlClient(SIM, 6001) as c:
        yield c


def get(name, as_string=False):
    value = epics.caget(P + name, as_string=as_string, use_monitor=False, timeout=3.0)
    assert value is not None, "%s does not answer" % name
    return value


def sevr(name):
    return get(name + ".SEVR")


def stat(name):
    return get(name + ".STAT", as_string=True)


def put(name, value):
    assert epics.caput(P + name, value, wait=True, timeout=10.0) == 1, "caput %s" % name


def wait_for(what, test, timeout=10.0):
    end = time.time() + timeout
    while True:
        value = what()
        if test(value):
            return value
        if time.time() > end:
            pytest.fail("timeout after %g s, last value %r" % (timeout, value))
        time.sleep(0.05)


def sent(x):
    """The number as the instrument sends it (13-4: 7 significant digits) and the IOC reads it."""
    return float("%+.6E" % x)


def counters(ctl):
    return {n: ctl.get(n)["value"] for n in ("n_set", "n_abort", "n_init", "n_query")}


def sim_log_mark():
    with open(os.path.join(BUILD, "sim.log")) as f:
        return len(f.readlines())


def sim_log_since(mark, pattern):
    with open(os.path.join(BUILD, "sim.log")) as f:
        return [l.rstrip() for l in f.readlines()[mark:] if pattern.search(l)]


def measuring(ctl):
    """Zero check off and the reading valid."""
    put("zcheck:set", 0)
    wait_for(lambda: sevr("current:get"), lambda s: s == 0, 5)


_restarts = [0]


def restart_ioc():
    pv = epics.PV("DEVTEST:heartbeat")
    assert pv.wait_for_connection(5)
    _restarts[0] += 1
    with open(os.path.join(BUILD, "ioc-restart"), "w") as f:
        f.write("%d\n" % _restarts[0])
    wait_for(lambda: pv.connected, lambda c: not c, 15)
    wait_for(lambda: pv.connected and pv.get(timeout=1) is not None, lambda c: c, 40)


# --- 2. the state after power-on ---------------------------------------------------------------

def test_power_on_state_is_shown_and_no_reading_is_a_measurement(ctl):
    """The simulator started in its power-on state (factory setup, manual Table 1-3): zero check
    ON, autoranging, NPLC 6. The requests took it over; the reading is INVALID."""
    wait_for(lambda: sevr("zcheck:get"), lambda s: s == 0, 10)
    wait_for(lambda: sevr("range:set"), lambda s: s == 0, 5)
    assert counters(ctl)["n_set"] == 0                     # nothing was set to get there
    assert get("zcheck:get", True) == "ON" and get("zcheck:set", True) == "ON"
    assert get("range:set", True) == "AUTO" and sevr("zcheck:set") == 0
    assert get("range:get", True) == "200 uA"                # power_on_range, Table 14-4
    assert get("nplc:get") == 6.0 and sevr("nplc:get") == 0
    assert get("idn:get.VAL$", True).startswith("MODEL 6485, ") and sevr("idn:get") == 0
    assert int(get("_status")) & 0x200                       # bit 9: zero check
    assert sevr("current:get") == INVALID and stat("current:get") == "STATE"

    # a power cycle while measuring: back to zero check ON, the reading INVALID, number kept
    measuring(ctl)
    ctl.set("current", 4.2e-7)
    try:
        wait_for(lambda: get("current:get"), lambda v: v == sent(4.2e-7), 5)
        ctl.set("power", 0)
        wait_for(lambda: sevr("current:get"), lambda s: s == INVALID, 4)
        ctl.set("power", 1)
        # the first poll after power-on can come before the first reading (-230, a short
        # answer: INVALID/CALC once); then zero check is read back ON
        wait_for(lambda: (get("zcheck:get", True), sevr("zcheck:get")),
                 lambda v: v == ("ON", 0), 5)
        time.sleep(2 * SCAN_S)
        assert sevr("current:get") == INVALID and stat("current:get") == "STATE"
        assert get("current:get") == sent(4.2e-7)            # the last measurement, kept
        assert get("_range:rb") == 0 and get("nplc:get") == 6.0
        assert get("zcheck:set", True) == "OFF"              # a request: what was last written
    finally:
        ctl.release("power")
        ctl.release("current")


# --- 1. normal operation: every range and autoranging ------------------------------------------

def test_every_pv_valid_and_the_reading_in_every_range(ctl):
    measuring(ctl)
    try:
        for state, r in enumerate(RANGES, start=1):
            put("range:set", state)
            assert sevr("range:set") == 0
            for x in (0.7345678912 * r, -0.2468013579 * r):
                ctl.set("current", x)
                wait_for(lambda: get("current:get"), lambda v: v == sent(x), 5)
            assert get("range:get") == state - 1 and get("_range:rb") == state
            assert ctl.get("auto")["value"] == 0.0
            assert [n for n in PUBLIC if sevr(n) != 0] == []
        put("range:set", 0)
        assert ctl.get("auto")["value"] == 1.0
        for i, r in enumerate(RANGES):                        # upwards: the lowest range that holds it
            x = 0.9 * r
            ctl.set("current", x)
            wait_for(lambda: get("current:get"), lambda v: v == sent(x), 5)
            wait_for(lambda: get("range:get"), lambda v: v == i, 3)
            assert get("_range:rb") == 0 and get("range:set", True) == "AUTO"
            assert [n for n in PUBLIC if sevr(n) != 0] == []
    finally:
        ctl.release("current")


# --- 3. overflow -------------------------------------------------------------------------------

def test_overflow_is_invalid_and_valid_again(ctl):
    measuring(ctl)
    try:
        put("range:set", 1)                                  # 2 nA, full scale 2.1 nA (4-2)
        ctl.set("current", 1.5e-9)
        wait_for(lambda: get("current:get"), lambda v: v == sent(1.5e-9), 5)
        ctl.set("current", 2.2e-9)
        wait_for(lambda: sevr("current:get"), lambda s: s == INVALID, 3)
        assert stat("current:get") == "STATE"
        assert get("_raw") == pytest.approx(9.9e37)          # what was sent
        assert get("current:get") == sent(1.5e-9)            # not the huge number
        assert int(get("_status")) & 1                       # bit 0 overflow
        assert [n for n in READBACKS[1:] if sevr(n) != 0] == []
        ctl.set("current", 1.9e-9)
        wait_for(lambda: sevr("current:get"), lambda s: s == 0, 3)
        assert get("current:get") == sent(1.9e-9)
        put("range:set", 0)                                  # autoranging: above 21 mA
        ctl.set("current", 0.025)
        wait_for(lambda: sevr("current:get"), lambda s: s == INVALID, 4)
        ctl.set("current", 0.015)
        wait_for(lambda: sevr("current:get"), lambda s: s == 0, 4)
        assert get("current:get") == sent(0.015)
    finally:
        ctl.release("current")


# --- 4. silent, garbage, closed ----------------------------------------------------------------

@pytest.mark.parametrize("mode", ["silent", "garbage", "close"])
def test_fault_is_invalid_in_time_and_recovers(ctl, mode):
    measuring(ctl)
    before = get("current:get")
    ctl.fault(mode)
    try:
        t0 = time.time()
        wait_for(lambda: [n for n in PUBLIC if n != "idn:get" and n != "range:set"
                          and n != "zcheck:set" and sevr(n) != INVALID],
                 lambda left: left == [], 5)
        took = time.time() - t0
        print("%s: every read-back INVALID after %.2f s (stated: within %.1f s)"
              % (mode, took, SCAN_S + REPLY_TIMEOUT_S + REPLY_TIMEOUT_S))
        assert took < SCAN_S + 2 * REPLY_TIMEOUT_S + 0.5
        for _ in range(10):
            assert get("current:get") == before                # no wrong value
            time.sleep(0.2)
        wait_for(lambda: sevr("idn:get"), lambda s: s == INVALID, 12)
    finally:
        ctl.clear(mode)
    t0 = time.time()
    wait_for(lambda: sevr("current:get"), lambda s: s == 0, 40)
    t_reading = time.time() - t0
    wait_for(lambda: [n for n in PUBLIC if sevr(n) != 0], lambda left: left == [], 40)
    print("%s cleared: current:get valid after %.1f s, every PV (idn:get: 10 s scan) after "
          "%.1f s, no IOC restart" % (mode, t_reading, time.time() - t0))


# --- 5. an IOC start takes over the state and sets nothing -------------------------------------

@pytest.mark.parametrize("zcheck,auto,rng,state", [(0, 0, 2e-6, 4), (1, 1, 2e-4, 0),
                                                    (0, 0, 2e-2, 8)])
def test_ioc_start_takes_over_the_state_and_sends_no_setting(ctl, zcheck, auto, rng, state):
    put("zcheck:set", 1 - zcheck)                            # the IOC's requests differ
    put("range:set", 1 if state != 1 else 2)
    for name, value in (("zero_check", zcheck), ("auto", auto), ("range", rng)):
        ctl.set(name, value)
    try:
        before, mark = counters(ctl), sim_log_mark()
        restart_ioc()
        wait_for(lambda: sevr("range:set"), lambda s: s == 0, 15)
        wait_for(lambda: sevr("zcheck:set"), lambda s: s == 0, 5)
        after = counters(ctl)
        assert get("range:set") == state
        assert get("zcheck:set") == zcheck and get("zcheck:get") == zcheck
        assert get("range:get") == RANGES.index(rng)
        assert sevr("current:get") == (INVALID if zcheck else 0)
        delta = {k: after[k] - before[k] for k in after}
        print("IOC start with zero check %d, auto %d, range %g: requests %s / %s, commands at "
              "the instrument: %s" % (zcheck, auto, rng, get("range:set", True),
                                      get("zcheck:set", True), delta))
        assert delta["n_set"] == 0
        assert sim_log_since(mark, SET_HEADS) == []
        assert ctl.get("zero_check")["value"] == zcheck and ctl.get("range")["value"] == rng
    finally:
        for name in ("zero_check", "auto", "range"):
            ctl.release(name)


# --- 6. the rate -------------------------------------------------------------------------------

def test_update_rate_against_the_arithmetic(ctl):
    measuring(ctl)
    put("range:set", 0)
    info = ctl.info()
    baud, bits = info["settings"]["baud"], info["settings"]["bits_per_char"]
    turn = info["settings"]["turnaround_ms"] / 1000.0
    nplc, f_line = get("nplc:get"), info["options"]["line_frequency"]
    t_reading = nplc / f_line * info["options"]["autozero_factor"]
    poll = "ABOR;:SYST:ZCH?;:CURR:RANG?;:CURR:RANG:AUTO?;:CURR:NPLC?;:SENS:DATA?\r"
    reply = "0; 2.000000E-07; 1; 6.000000E+00; +1.000000E-07A, +1.234567E+03, +0.000000E+00\r"
    t_line = (len(poll) + len(reply) + len("INIT\r")) * bits / baud + turn
    print("arithmetic: reading %.3f s (NPLC %g, %g Hz, autozero x%g), poll on the line %.3f s, "
          "sum %.3f s < scan %.1f s" % (t_reading, nplc, f_line,
                                       info["options"]["autozero_factor"], t_line,
                                       t_reading + t_line, SCAN_S))
    assert t_reading + t_line < SCAN_S

    stamps = []
    pv = epics.PV(P + "_stamp", auto_monitor=True)
    pv.add_callback(lambda value=None, **kw: stamps.append((time.time(), value)))
    pv.wait_for_connection(5)
    time.sleep(1.5)
    ctl.stats(reset=True)
    del stamps[:]
    time.sleep(10.0)
    s = ctl.stats()
    pv.clear_callbacks()
    steps = [b[1] - a[1] for a, b in zip(stamps, stamps[1:])]
    rate = (len(stamps) - 1) / (stamps[-1][0] - stamps[0][0])
    print("measured: %d new readings in 10 s, %.3f Hz; timestamp steps %.3f .. %.3f s; "
          "simulator %.2f messages/s, line busy %.1f %%"
          % (len(stamps), rate, min(steps), max(steps), s["requests"] / s["elapsed_s"],
             100 * s["busy_s"] / s["elapsed_s"]))
    assert rate == pytest.approx(1.0 / SCAN_S, rel=0.1)
    assert all(step > 0 for step in steps)                  # every poll a new reading
    assert all(abs(step - SCAN_S) <= t_reading + 0.1 for step in steps)


# --- the IOC log -------------------------------------------------------------------------------

ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
EXPECTED = re.compile(r"No reply|does not match|mismatch|Timeout|timed out|connect|Connection"
                      r"|disconnect|Broken pipe|reset by peer|still busy|asynManager"
                      r"|additional errors of the following type|input .* too short", re.I)


def test_ioc_log_has_no_database_protocol_or_link_error():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    done = [i for i, l in enumerate(lines) if "iocRun: All initialization complete" in l]
    assert done, "IOC did not finish iocInit"
    init = lines[:done[0]]
    assert [l for l in init if ERROR.search(l) and not l.startswith("on error ")] == []
    run = lines[done[0]:]
    assert [l for l in run if ERROR.search(l) and not EXPECTED.search(l)
            and not l.startswith("on error ")] == []       # st.cmd again after a restart
