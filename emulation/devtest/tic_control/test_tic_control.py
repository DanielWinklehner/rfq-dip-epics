"""Edwards TIC (T32): the requests of tic_control.db (beside tic.db, with first_contact.db) in a
real IOC against the edwards_tic simulator: each request with its acknowledgement and read-back,
each refusal with its word, the gauge's slave setup, an error reply and a missing reply, the
take-over after an IOC restart, a command while the line is polled at the full rate.

The tests run in this order and hand the station on: both pumps running and the AIM on at the
start (sim.yaml), as at the end. A run-down is cut short over the simulator's control port (the
speed set to 0, as if the pump had stopped): no test waits for a run-down or relies on a start
while the pump brakes (not tried on the controller)."""

import math
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

BUILD = os.environ["DEVTEST_BUILD"]
SIM = os.environ["SIM_HOST"]
NO_ALARM, MINOR, MAJOR, INVALID = 0, 1, 2, 3
STAT_LINK, STAT_TIMEOUT, STAT_CALC = 14, 10, 12

TURBO, BACKING, AIM = "TIC:turbo:start:set", "TIC:backing:start:set", "TIC:gauge2:on:set"
RB = {TURBO: "TIC:turbo:start:get", BACKING: "TIC:backing:start:get", AIM: "TIC:gauge2:on:get"}
REASON = {TURBO: "TIC:turbo:start:reason", BACKING: "TIC:backing:start:reason", AIM: "TIC:gauge2:on:reason"}
APG = "TIC:gauge1:getpressure"
FOLLOW = 6.0        # s: a read-back after an acknowledged command (turbopump: 1 s delay, polled every 2 s)


@pytest.fixture(scope="module")
def ctl():
    with ControlClient(SIM, 6034) as c:
        yield c


def get(name, as_string=False):
    return epics.caget(name, as_string=as_string, use_monitor=False, timeout=2.0)


def word(name):
    return get(name, as_string=True)


def sevr(name):
    return epics.caget(name + ".SEVR", use_monitor=False, timeout=2.0)


def stat(name):
    return epics.caget(name + ".STAT", use_monitor=False, timeout=2.0)


def put(name, value):
    """A client's write, waiting for its completion (the acknowledgement or the reply timeout)."""
    assert epics.caput(name, value, wait=True, timeout=5.0) == 1, name


def wait_for(what, test, timeout=10.0, why=""):
    end = time.time() + timeout
    while True:
        value = what()
        if test(value):
            return value
        if time.time() > end:
            pytest.fail("timeout after %g s%s, last value %r" % (timeout, " (%s)" % why if why else "", value))
        time.sleep(0.1)


def commands(ctl):
    return ctl.get("commands")["value"]


def sig(ctl, name):
    return ctl.get(name)["value"]


def settle(names, timeout=10.0):
    for n in names:
        wait_for(lambda: sevr(n), lambda s: s == NO_ALARM, timeout, n)


def stop_turbo_now(ctl):
    """The run-down cut short: the speed 0 over the control port, released (the simulator then
    finds the pump stopped)."""
    ctl.set("turbo.speed", 0.0)
    ctl.release("turbo.speed")
    wait_for(lambda: word("TIC:turbo:state:get"), lambda w: w == "Stopped", 5.0)


class Seen:
    """The severities and values a PV posts while it is watched (the fall-back of a refused request
    comes 20 ms after the refusal: too soon for a read after the write)."""

    def __init__(self, name):
        self.events = []
        self.pv = epics.PV(name, auto_monitor=True, form="time")
        self.pv.wait_for_connection(2.0)
        self.pv.add_callback(lambda value=None, severity=None, status=None, **kw:
                             self.events.append((value, severity, status)))
        time.sleep(0.3)
        self.events.clear()

    def close(self):
        self.pv.clear_callbacks()
        self.pv.disconnect()


def refused(ctl, req, value, reason):
    """A refused write: INVALID (LINK) at once, nothing sent, back to the read-back's value without
    alarm, and the reason's word."""
    before, sent = get(req), commands(ctl)
    seen = Seen(req)
    try:
        put(req, value)
        time.sleep(0.5)
    finally:
        seen.close()
    assert (value, INVALID, STAT_LINK) in seen.events, (req, seen.events, epics.caget(req.rsplit(":", 2)[0] + ":_refuse"))
    wait_for(lambda: (get(req), sevr(req)), lambda v: v == (get(RB[req]), NO_ALARM), 2.0, "fall-back of %s" % req)
    assert get(req) == before, (req, before, get(req))
    assert word(REASON[req]) == reason
    assert epics.caget(req + ".SIMM", as_string=True) == "NO"
    time.sleep(0.5)
    assert commands(ctl) == sent, "a refused request sent a command"
    print("%s := %d refused: %r, back to %d, nothing sent" % (req, value, reason, get(req)))


def acknowledged(ctl, req, value, rb_value=None):
    sent = commands(ctl)
    t0 = time.time()
    put(req, value)
    took = time.time() - t0
    assert sevr(req) == NO_ALARM, (req, sevr(req), stat(req), word(REASON[req]))
    assert word(REASON[req]) == "Acknowledged"
    assert commands(ctl) == sent + 1
    if rb_value is not None:
        wait_for(lambda: get(RB[req]), lambda v: v == rb_value, FOLLOW, "read-back of %s" % req)
    print("%s := %d acknowledged after %.0f ms, read-back %s" % (req, value, 1000 * took, word(RB[req])))


# --- the start: what the station has, taken over --------------------------------------------

def test_requests_hold_the_station_state_after_the_start():
    for req in (TURBO, BACKING, AIM):
        settle([req, RB[req]], 20.0)
        assert get(req) == 1 and get(RB[req]) == 1, req
        assert word(REASON[req]) == "No request since start"
    assert word(RB[TURBO]) == "run" and word("TIC:turbo:atspeed:get") == "at speed"
    assert word(RB[AIM]) == "on"


# --- refusals and the order of a shut-down --------------------------------------------------

def test_backing_pump_stop_is_refused_while_the_turbopump_runs(ctl):
    refused(ctl, BACKING, 0, "Refused: turbopump runs")
    assert word("TIC:backing:state:get") == "On"


def test_turbopump_stop_is_acknowledged_and_read_back(ctl):
    acknowledged(ctl, TURBO, 0, 0)
    assert word("TIC:turbo:state:get") == "Braking"
    assert word(RB[TURBO]) == "stop"


def test_backing_pump_stop_while_the_turbopump_brakes(ctl):
    """The order used on the lab's TIC: the turbopump's stop, the backing pump off right after."""
    assert word("TIC:turbo:state:get") == "Braking"
    acknowledged(ctl, BACKING, 0, 0)
    assert word("TIC:backing:state:get") == "Off"


def test_turbopump_start_is_refused_while_the_backing_pump_is_off(ctl):
    stop_turbo_now(ctl)
    refused(ctl, TURBO, 1, "Refused: backing not on")
    assert get(RB[TURBO]) == 0


def test_turbopump_start_is_refused_while_the_backing_state_is_not_known(ctl):
    ctl.set("backing.absent", 1)                      # error replies to ?V910: state not known
    try:
        wait_for(lambda: sevr("TIC:backing:state:get"), lambda s: s == INVALID, 6.0)
        refused(ctl, TURBO, 1, "Refused: backing unknown")
    finally:
        ctl.release("backing.absent")
    settle(["TIC:backing:state:get"])


def test_start_again_backing_pump_first(ctl):
    acknowledged(ctl, BACKING, 1, 1)
    acknowledged(ctl, TURBO, 1, 1)
    assert word("TIC:turbo:state:get") in ("Accelerating", "Running")
    assert word("TIC:turbo:atspeed:get") == "no"
    ctl.set("turbo.speed", 100.0)                     # the run-up cut short
    ctl.release("turbo.speed")
    wait_for(lambda: word("TIC:turbo:atspeed:get"), lambda w: w == "at speed", 5.0)
    assert word("TIC:turbo:state:get") == "Running"


def test_backing_pump_stop_is_refused_while_the_turbopump_state_is_not_known(ctl):
    ctl.set("turbo.absent", 1)
    try:
        wait_for(lambda: sevr("TIC:turbo:state:get"), lambda s: s == INVALID, 6.0)
        assert sevr(RB[TURBO]) == INVALID
        refused(ctl, BACKING, 0, "Refused: turbo unknown")
    finally:
        ctl.release("turbo.absent")
    settle([RB[TURBO], "TIC:turbo:state:get"])


# --- the gauge on socket 2 (the AIM) ---------------------------------------------------------

def test_gauge_off_is_acknowledged(ctl):
    acknowledged(ctl, AIM, 0, 0)
    assert word("TIC:gauge2:state:get") == "Off"
    assert sevr("TIC:gauge2:getpressure") == INVALID


def test_gauge_on_is_refused_above_the_owners_limit(ctl):
    ctl.set("g1.pressure", 1.1e-2)
    try:
        wait_for(lambda: get(APG), lambda p: p > 1.05e-2, 5.0)
        assert sevr(APG) == NO_ALARM
        refused(ctl, AIM, 1, "Refused: APG > 1e-2 torr")
    finally:
        ctl.release("g1.pressure")


def test_gauge_on_is_refused_while_the_apg_is_not_valid(ctl):
    ctl.set("g1.state", 5)                            # the APG off: its pressure INVALID
    try:
        wait_for(lambda: sevr(APG), lambda s: s == INVALID, 5.0)
        refused(ctl, AIM, 1, "Refused: APG not valid")
    finally:
        ctl.release("g1.state")
    settle([APG])


def test_gauge_on_below_the_limit_strikes_and_reads(ctl):
    assert get(APG) <= 1e-2
    acknowledged(ctl, AIM, 1, 1)
    wait_for(lambda: word("TIC:gauge2:state:get"), lambda w: w == "On", 5.0)
    first = get("TIC:gauge2:getpressure")
    time.sleep(3.0)
    assert get("TIC:gauge2:getpressure") == first     # the standing value (5 s here, 146 s seen)
    print("gauge 2 on: %s, standing value %.6e torr" % (word("TIC:gauge2:state:get"), first))


# --- the slave setup, read only --------------------------------------------------------------

def test_slave_setup_not_linked(ctl):
    wait_for(lambda: word("TIC:gauge2:slave:get"), lambda w: w == "not linked", 12.0)
    assert get("TIC:gauge2:slave:master:get") == 913
    assert get("TIC:gauge2:slave:on:get") == pytest.approx(1.0e-2, rel=1e-3)
    assert get("TIC:gauge2:slave:off:get") == pytest.approx(2.0e-2, rel=1e-3)
    assert get("TIC:gauge2:slave:raw", as_string=True) == "4;913;59;1.3332e+00;2.6664e+00;0"


def test_slave_setup_linked(ctl):
    ctl.set("g2.slave_enable", 1)
    try:
        wait_for(lambda: word("TIC:gauge2:slave:get"), lambda w: w == "linked", 12.0)
        assert sevr("TIC:gauge2:slave:get") == NO_ALARM
        print("slave setup: %s at %.3g torr (raw %r)" % (word("TIC:gauge2:slave:get"),
              get("TIC:gauge2:slave:on:get"), get("TIC:gauge2:slave:raw", as_string=True)))
    finally:
        ctl.release("g2.slave_enable")


def test_slave_setup_reply_of_another_form_is_invalid_and_kept(ctl):
    ctl.set("g2.slave_form", 1)                       # the manual's example form, no config type
    try:
        wait_for(lambda: sevr("TIC:gauge2:slave:get"), lambda s: s == INVALID, 12.0)
        assert word("TIC:gauge2:slave:get") == "No valid reply"
        assert sevr("TIC:gauge2:slave:on:get") == INVALID
        assert get("TIC:gauge2:slave:raw", as_string=True) == "913;59;1.3e+00;2.7e+00;0"
    finally:
        ctl.release("g2.slave_form")
    wait_for(lambda: word("TIC:gauge2:slave:get"), lambda w: w == "not linked", 12.0)


# --- an error reply, no reply -----------------------------------------------------------------

def test_error_reply_leaves_the_request_in_alarm_with_the_word(ctl):
    ctl.set("command_code", 5)
    try:
        sent = commands(ctl)
        put(BACKING, 1)                               # already on: the TIC answers code 5
        assert sevr(BACKING) == INVALID and stat(BACKING) == STAT_CALC
        assert word(REASON[BACKING]) == "Invalid cmd in this state"
        assert commands(ctl) == sent + 1
        time.sleep(2.5)
        assert get(RB[BACKING]) == 1 and sevr(BACKING) == INVALID   # the pump unchanged
    finally:
        ctl.release("command_code")
    acknowledged(ctl, BACKING, 1, 1)


def test_missing_reply_leaves_the_request_in_alarm(ctl):
    ctl.fault("silent")
    try:
        put(AIM, 0)
        assert sevr(AIM) == INVALID and stat(AIM) == STAT_TIMEOUT
        assert word(REASON[AIM]) == "No reply"
    finally:
        ctl.clear("silent")
    settle([RB[AIM]])
    assert get(RB[AIM]) == 1                          # not executed
    acknowledged(ctl, AIM, 1, 1)


# --- a command while the line is polled ------------------------------------------------------

def test_command_while_the_line_is_polled_at_the_full_rate(ctl):
    watched = [APG, "TIC:gauge2:getpressure", "TIC:turbo:state:get", "TIC:backing:state:get",
               "TIC:turbo:speed:get", "TIC:ident:get"]
    settle(watched)
    ctl.stats(reset=True)
    bad = []
    for _ in range(10):
        acknowledged(ctl, BACKING, 1)                 # already on: the TIC acknowledges, no change
        bad += [n for n in watched if sevr(n) != NO_ALARM]
        time.sleep(0.4)
    s = ctl.stats()
    rate = s["requests"] / s["elapsed_s"]
    print("10 commands among the polls: %.2f requests/s, line busy %.1f %%, %d readings not valid"
          % (rate, 100 * s["busy_s"] / s["elapsed_s"], len(bad)))
    assert bad == []
    assert s["heads"].get("!") == 10


# --- the take-over after an IOC restart ------------------------------------------------------

def restart_ioc():
    path = os.path.join(BUILD, "ioc-restart")
    with open(path) as f:
        n = len(f.read())
    with open(path, "w") as f:
        f.write("x" * (n + 1))


def test_restart_with_the_pumps_running_sends_nothing(ctl):
    settle([RB[TURBO], RB[BACKING], RB[AIM]])
    sent = commands(ctl)
    restart_ioc()
    time.sleep(3.0)
    wait_for(lambda: epics.caget("DEVTEST:heartbeat", timeout=1.0), lambda v: v is not None and v >= 1, 60.0)
    for req in (TURBO, BACKING, AIM):
        wait_for(lambda: (get(req), sevr(req)), lambda v: v == (1, NO_ALARM), 10.0, "take-over of %s" % req)
        assert epics.caget(req + ".SIMM", as_string=True) == "NO"
        assert word(REASON[req]) == "No request since start"
    time.sleep(2.0)
    assert commands(ctl) == sent, "the restart sent a command"
    assert (sig(ctl, "turbo.state"), sig(ctl, "backing.state"), sig(ctl, "g2.state")) == (4, 4, 11)
    acknowledged(ctl, TURBO, 1, 1)                    # afterwards a request is sent as before


# --- the lag of the TIC's state after an acknowledged command (the lead's review of T32) --------
# On the lab's TIC the turbopump showed its old state 51 ms after "!C904 1" and the new one by
# 5 s; the IOC polls every 2 s on top. Within that time the other pump's request must still be
# refused: the IOC holds an acknowledged turbopump start and an acknowledged backing pump stop
# for HOLD_S (tic_control.db). The second write follows the first one's acknowledgement at once.

def stopped_turbo_and_backing_on(ctl):
    if get(RB[BACKING]) != 1:
        acknowledged(ctl, BACKING, 1, 1)
    if get(RB[TURBO]) == 1:
        acknowledged(ctl, TURBO, 0, 0)
    stop_turbo_now(ctl)


def straight_after(ctl, first, first_value, second, second_value, word_expected):
    """The first request acknowledged, the second written at once (no wait for a read-back):
    refused with the word, nothing sent, back at the read-back's value."""
    sent = commands(ctl)
    put(first, first_value)
    put(second, second_value)
    got = (sevr(second), stat(second), word(REASON[first]), word(REASON[second]))
    shown = word("TIC:turbo:state:get"), word("TIC:backing:state:get")
    after = commands(ctl)
    print("%s := %d, then %s := %d at once: %r, commands +%d, states shown %r"
          % (first, first_value, second, second_value, got, after - sent, shown))
    assert got[2] == "Acknowledged", got
    assert got[3] == word_expected, got
    assert after == sent + 1, "the second request was sent"
    wait_for(lambda: (get(second), sevr(second)), lambda v: v == (get(RB[second]), NO_ALARM), 2.0)


def test_backing_pump_stop_straight_after_a_turbopump_start_is_refused(ctl):
    stopped_turbo_and_backing_on(ctl)
    try:
        straight_after(ctl, TURBO, 1, BACKING, 0, "Refused: turbopump runs")
        assert sig(ctl, "backing.state") == 4
    finally:
        if sig(ctl, "backing.state") != 4:
            acknowledged(ctl, BACKING, 1)
        ctl.set("turbo.speed", 100.0)
        ctl.release("turbo.speed")
        wait_for(lambda: word("TIC:turbo:state:get"), lambda w: w == "Running", 6.0)


def test_turbopump_start_straight_after_a_backing_pump_stop_is_refused(ctl):
    stopped_turbo_and_backing_on(ctl)
    try:
        straight_after(ctl, BACKING, 0, TURBO, 1, "Refused: backing not on")
        assert sig(ctl, "turbo.state") == 0
    finally:
        acknowledged(ctl, BACKING, 1, 1)              # ends the hold of the backing pump's stop
        if sig(ctl, "turbo.state") == 0:
            acknowledged(ctl, TURBO, 1, 1)            # the order of a start: backing pump first
        ctl.set("turbo.speed", 100.0)
        ctl.release("turbo.speed")
        wait_for(lambda: word("TIC:turbo:state:get"), lambda w: w == "Running", 6.0)


ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)
EXPECTED = re.compile(r"No reply|does not match|mismatch|Timeout|timed out|connect|Connection"
                      r"|disconnect|Broken pipe|reset by peer|still busy|asynManager|restarted"
                      r"|additional errors of the following type", re.I)


def test_ioc_log_has_no_database_protocol_or_link_error():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    done = [i for i, l in enumerate(lines) if "iocRun: All initialization complete" in l]
    assert done, "IOC did not finish iocInit"
    lines = [l for l in lines if not l.startswith("on error ")]
    init = [l for l in lines[:done[0]]]
    assert [l for l in init if ERROR.search(l)] == []
    run = lines[done[0]:]                             # includes the restarted IOC's start
    assert [l for l in run if ERROR.search(l) and not EXPECTED.search(l)] == []
