"""Edwards TIC (T29): tic.db and tic.proto in a real IOC against the edwards_tic simulator."""

import math
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

BUILD = os.environ["DEVTEST_BUILD"]
SIM = os.environ["SIM_HOST"]
INVALID = 3
G1, G2, G3 = ("TIC:gauge%d:getpressure" % n for n in (1, 2, 3))


@pytest.fixture(scope="module")
def ctl():
    with ControlClient(SIM, 6034) as c:
        yield c


def get(name, as_string=False):
    return epics.caget(name, as_string=as_string, use_monitor=False, timeout=2.0)


def sevr(name):
    return epics.caget(name + ".SEVR", use_monitor=False, timeout=2.0)


def word(name):
    return get(name, as_string=True)


def wait_for(what, test, timeout=10.0):
    end = time.time() + timeout
    while True:
        value = what()
        if test(value):
            return value
        if time.time() > end:
            pytest.fail("timeout after %g s, last value %r" % (timeout, value))
        time.sleep(0.1)


def valid(name, timeout=15):
    return wait_for(lambda: sevr(name), lambda s: s == 0, timeout)


def invalid(name, timeout=6):
    wait_for(lambda: sevr(name), lambda s: s == INVALID, timeout)
    time.sleep(0.3)                     # the value of the same processing
    assert sevr(name) == INVALID


def nan(name):
    value = get(name)
    assert value is not None and math.isnan(value), "%s = %r, not NaN" % (name, value)


def test_every_reading_has_a_value():
    valid(G1)
    valid(G2)
    valid("TIC:turbo:state:get")
    valid("TIC:ident:get")
    assert get(G1) == pytest.approx(1.0e-6, rel=0.06)
    assert get(G2) == pytest.approx(5.0e-3, rel=0.06)
    assert epics.PV(G1).get_ctrlvars(timeout=2)["units"] == "torr"
    for n in (1, 2):
        assert word("TIC:gauge%d:state:get" % n) == "On"
        assert word("TIC:gauge%d:units:get" % n) == "PRESSURE (Pa)"
        assert word("TIC:gauge%d:priority:get" % n) == "OK"
        assert get("TIC:gauge%d:alert:get" % n) == 0
    assert word("TIC:turbo:state:get") == "Running"
    assert word("TIC:turbo:type:get") == "nEXT - 232"
    assert get("TIC:turbo:speed:get") == pytest.approx(100.0)
    assert sevr("TIC:turbo:speed:get") == 0
    assert get("TIC:turbo:alert:get") == 0
    assert word("TIC:variant:get") == "TIC"
    assert get("TIC:ident:get", as_string=True) == "TIC;DSIM00000;SIM0001;SIM"
    assert word("TIC:model:get") == "TIC"
    assert word("TIC:sw:get") == "DSIM00000"
    print("gauge 1 %.3e torr, gauge 2 %.3e torr, turbo %s at %.1f %%"
          % (get(G1), get(G2), word("TIC:turbo:state:get"), get("TIC:turbo:speed:get")))


def test_socket_without_gauge_is_invalid():
    invalid(G3)
    nan(G3)
    assert word("TIC:gauge3:state:get") == "Gauge Not connected"


@pytest.mark.parametrize("state, text", [(5, "Off"), (6, "Striking"), (4, "Gauge In Alert")])
def test_gauge_not_on_is_invalid(ctl, state, text):
    valid(G1)
    ctl.set("g1.state", state)
    try:
        invalid(G1)
        nan(G1)
        assert word("TIC:gauge1:state:get") == text
        assert sevr(G2) == 0                         # the other gauge is not affected
    finally:
        ctl.release("g1.state")
    valid(G1, 5)
    assert word("TIC:gauge1:state:get") == "On"


def test_controller_without_backing_pump_is_invalid():
    invalid("TIC:backing:state:get")
    assert word("TIC:backing:state:get") == "No Pump"
    assert word("TIC:backing:type:get") == "No Pump"


def test_object_the_controller_does_not_have_is_invalid(ctl):
    valid("TIC:turbo:speed:get")
    ctl.set("turbo.absent", 1)                       # error replies "*V904 2", "*S904 2"
    try:
        invalid("TIC:turbo:state:get")
        assert word("TIC:turbo:state:get") == "Invalid query/command"
        assert word("TIC:turbo:type:get") == "Invalid query/command"
        invalid("TIC:turbo:speed:get")
        nan("TIC:turbo:speed:get")
    finally:
        ctl.release("turbo.absent")
    valid("TIC:turbo:state:get", 8)
    assert word("TIC:turbo:state:get") == "Running"


def test_turbo_without_pump_is_invalid(ctl):
    ctl.set("turbo.type", 0)
    try:
        invalid("TIC:turbo:state:get")
        assert word("TIC:turbo:state:get") == "No Pump"
        invalid("TIC:turbo:speed:get")
        nan("TIC:turbo:speed:get")
    finally:
        ctl.release("turbo.type")
    valid("TIC:turbo:speed:get", 8)


def test_reply_in_another_unit_is_invalid(ctl):
    valid(G1)
    ctl.set("g1.units", 66)                          # voltage mode, 1.7.4
    try:
        invalid(G1)
        nan(G1)
        assert word("TIC:gauge1:units:get") == "VOLTAGE"
        assert word("TIC:gauge1:state:get") == "On"
    finally:
        ctl.release("g1.units")
    valid(G1, 5)


def test_silent_controller_is_invalid_and_recovers(ctl):
    names = [G1, G2, "TIC:turbo:state:get", "TIC:turbo:speed:get", "TIC:gauge1:state:get",
             "TIC:variant:get", "TIC:ident:get"]
    for name in names:
        valid(name)
    ctl.fault("silent")
    try:
        t0 = time.time()
        for name in names:
            invalid(name, 8)
        print("silent: all INVALID after %.1f s" % (time.time() - t0))
        nan(G1)
        nan("TIC:turbo:speed:get")
    finally:
        ctl.clear("silent")
    t0 = time.time()
    for name in names:
        valid(name, 10)
    print("answering again: all valid after %.1f s" % (time.time() - t0))
    assert get(G1) == pytest.approx(1.0e-6, rel=0.06)


def test_poll_rate_and_line_load(ctl):
    ctl.stats(reset=True)
    time.sleep(10.0)
    s = ctl.stats()
    rate = s["requests"] / s["elapsed_s"]
    busy = s["busy_s"] / s["elapsed_s"]
    print("TIC: %.2f requests/s (3 gauges at 1 s + 7 queries at 2 s = 6.5), line busy %.1f %%"
          % (rate, 100 * busy))
    assert rate == pytest.approx(6.5, rel=0.15)


def test_ioc_sent_only_queries(ctl):
    ctl.stats(reset=True)
    time.sleep(4.0)
    heads = ctl.stats()["heads"]
    print("first characters of the requests in 4 s: %r" % heads)
    assert set(heads) == {"?"}
    assert ctl.get("commands")["value"] == 0.0       # since the simulator started


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
    # an error reply is a known answer, not a protocol error: no "does not match" for it
    assert [l for l in run if "does not match" in l and "*" in l] == []
