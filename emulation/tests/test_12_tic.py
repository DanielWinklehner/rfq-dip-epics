"""The Edwards TIC station's requests (tic_control.db, task T32) in the full emulation: the cart's
turbopump and backing pump started and stopped, the AIM on socket 2 switched, as the other
requests are tested in test_03_write (write and read-back) and test_04_ack (a set to a silent
device alarms and is not executed), here in the order the station needs: the IOC refuses a
backing pump stop under a running turbopump, a turbopump start without the backing pump, and
the AIM's switch-on unless the APG reads 1e-2 torr or lower. Each refusal sends nothing, falls
back at once and says why. The stop of the turbopump with the foreline valve open is not refused
(the owner's word: a warning in the GUI). The first contact is in test_11_first_contact, the
fault lists in test_05_faults.

A run-down or a run-up is cut short over the simulator's control port (the speed set to 0 or
100 %, then released): no test waits for the turbopump (105 s and more seen) or relies on a
start while it brakes (not tried on the controller). The station is left as the suite found it:
both pumps running, the AIM on."""
import time

import pytest

import system as S
from system import reg
from conftest import snapshot

SIM = "tic"
ECHO_LIMIT = 6.0     # s: the TIC's pumps are read every 2 s (the turbopump's state 1 s late, the
                     # simulator's ASSUMED delay), the gauges every 1 s
BACK_LIMIT = 2.0     # s: a refused request back to the read-back's value (0.02 s in the IOC)


def channel(name):
    return reg.devices["tic"]["channels"][name]["roles"]


TURBO, BACKING, AIM = channel("turbo"), channel("backing"), channel("gauge2")
APG = channel("gauge1")["p"]
FORELINE = "VALVE:s1:set"


def commands():
    return S.sim_value(SIM, "commands")


def tic_state(roles):
    return S.get(roles["state"], as_string=True)


def acknowledged(roles, cmd, value, rb_value=None):
    sent = commands()
    S.put(roles[cmd], value)
    assert S.sevr(roles[cmd]) == S.NO_ALARM, S.describe([roles[cmd], roles["result"]])
    assert S.get(roles["result"], as_string=True) == "Acknowledged"
    assert commands() == sent + 1
    if rb_value is not None:
        rb = roles["run_state" if cmd == "run_cmd" else "enable_state"]
        S.wait_for(lambda: S.get(rb) == rb_value, ECHO_LIMIT, lambda: "read-back: %s" % S.describe([rb]))


def refused(roles, cmd, value, word):
    req = roles[cmd]
    rb = roles["run_state" if cmd == "run_cmd" else "enable_state"]
    before, sent = S.get(req), commands()
    S.put(req, value)
    S.wait_for(lambda: S.get(req) == S.get(rb) and S.sevr(req) == S.NO_ALARM, BACK_LIMIT,
               lambda: "the refused request back: %s" % S.describe([req, rb]))
    assert S.get(req) == before
    assert S.get(roles["result"], as_string=True) == word
    time.sleep(0.5)
    assert commands() == sent, "a refused request sent a command"


def unanswered(roles, cmd, value):
    """A set to the silent TIC: INVALID on the request, not executed."""
    req = roles[cmd]
    rb = roles["run_state" if cmd == "run_cmd" else "enable_state"]
    before = S.get(rb)
    with S.fault(SIM, "silent"):
        S.put(req, value)
        assert S.sevr(req) == S.INVALID, S.describe([req])
        assert S.get(roles["result"], as_string=True) == "No reply"
    S.wait_for(lambda: S.sevr(rb) == S.NO_ALARM, ECHO_LIMIT, lambda: S.describe([rb]))
    time.sleep(2.5)
    assert S.get(rb) == before, "the silent TIC executed %s := %r" % (req, value)


def cut_short(speed, state):
    S.sim_set(SIM, "turbo.speed", speed)
    S.sim_release(SIM, "turbo.speed")
    S.wait_for(lambda: tic_state(TURBO) == state, ECHO_LIMIT, lambda: S.describe([TURBO["state"]]))


@pytest.fixture(scope="module")
def station():
    """The station as the suite found it, and put back afterwards."""
    for roles in (TURBO, BACKING, AIM):
        S.wait_for(lambda: S.sevr(roles["result"]) == S.NO_ALARM and S.get(roles.get("run_state", roles.get("enable_state"))) == 1,
                   30.0, lambda: S.describe(list(roles.values())))
    foreline = S.get(FORELINE)
    yield
    S.clear_everything()
    if S.get(BACKING["run_state"]) != 1:
        S.put(BACKING["run_cmd"], 1)
    if S.get(TURBO["run_state"]) != 1:
        if tic_state(TURBO) == "Braking":
            cut_short(0.0, "Stopped")
        S.put(TURBO["run_cmd"], 1)
    if tic_state(TURBO) != "Running" or S.get(TURBO["atspeed"]) != 1:
        cut_short(100.0, "Running")
    if S.get(AIM["enable_state"]) != 1:
        S.put(AIM["enable"], 1)
    S.put(FORELINE, foreline)
    for name in (TURBO["run_cmd"], BACKING["run_cmd"], AIM["enable"]):
        S.wait_for(lambda: S.get(name) == snapshot[name]["value"] and S.sevr(name) == S.NO_ALARM, ECHO_LIMIT,
                   lambda: "%s back: %s" % (name, S.describe([name])))


def test_the_requests_and_their_read_backs(station):
    for roles, cmd, rb in ((TURBO, "run_cmd", "run_state"), (BACKING, "run_cmd", "run_state"),
                           (AIM, "enable", "enable_state")):
        assert reg.pvs[roles[cmd]]["ack"] and reg.pvs[roles[cmd]]["readback"] == roles[rb]
        assert (S.get(roles[cmd]), S.get(roles[rb])) == (1, 1), S.describe([roles[cmd], roles[rb]])
    assert S.get(TURBO["atspeed"], as_string=True) == "at speed"
    assert reg.devices["tic"]["channels"]["turbo"]["class"] == "turbo"


def test_backing_pump_stop_refused_while_the_turbopump_runs(station):
    refused(BACKING, "run_cmd", 0, "Refused: turbopump runs")
    assert tic_state(BACKING) == "On"


def test_sets_to_the_silent_tic_alarm_and_are_not_executed(station):
    unanswered(AIM, "enable", 0)
    acknowledged(AIM, "enable", 1, 1)               # written again: no alarm
    unanswered(TURBO, "run_cmd", 0)
    acknowledged(TURBO, "run_cmd", 1, 1)


def test_turbopump_stop_with_the_foreline_valve_open_is_not_refused(station):
    S.put(FORELINE, 1)
    S.wait_for(lambda: S.get("VALVE:s1:get") == 1, ECHO_LIMIT, "foreline valve open")
    acknowledged(TURBO, "run_cmd", 0, 0)
    assert tic_state(TURBO) == "Braking"
    S.put(FORELINE, 0)


def test_backing_pump_stop_while_the_turbopump_brakes(station):
    assert tic_state(TURBO) == "Braking"
    unanswered(BACKING, "run_cmd", 0)
    acknowledged(BACKING, "run_cmd", 0, 0)
    assert tic_state(BACKING) == "Off"


def test_turbopump_start_refused_without_the_backing_pump(station):
    cut_short(0.0, "Stopped")
    refused(TURBO, "run_cmd", 1, "Refused: backing not on")


def test_start_backing_pump_first(station):
    acknowledged(BACKING, "run_cmd", 1, 1)
    acknowledged(TURBO, "run_cmd", 1, 1)
    assert S.get(TURBO["atspeed"], as_string=True) == "no"
    cut_short(100.0, "Running")
    S.wait_for(lambda: S.get(TURBO["atspeed"], as_string=True) == "at speed", ECHO_LIMIT,
               lambda: S.describe([TURBO["atspeed"]]))


def test_aim_off_and_its_refusals(station):
    acknowledged(AIM, "enable", 0, 0)
    S.sim_set(SIM, "g1.pressure", 1.1e-2)
    try:
        S.wait_for(lambda: S.get(APG) > 1.05e-2, ECHO_LIMIT, lambda: S.describe([APG]))
        refused(AIM, "enable", 1, "Refused: APG > 1e-2 torr")
    finally:
        S.sim_release(SIM, "g1.pressure")
    S.sim_set(SIM, "g1.state", 5)
    try:
        S.wait_for(lambda: S.sevr(APG) == S.INVALID, ECHO_LIMIT, lambda: S.describe([APG]))
        refused(AIM, "enable", 1, "Refused: APG not valid")
    finally:
        S.sim_release(SIM, "g1.state")
    S.wait_for(lambda: S.sevr(APG) == S.NO_ALARM and S.get(APG) <= 1e-2, ECHO_LIMIT, lambda: S.describe([APG]))
    acknowledged(AIM, "enable", 1, 1)
    S.wait_for(lambda: S.get(AIM["state"], as_string=True) == "On", ECHO_LIMIT, lambda: S.describe([AIM["state"]]))


def test_the_aims_slave_setup_is_read(station):
    """The emulation's AIM has no slave link, as the lab's TIC behaved (D9a)."""
    S.wait_for(lambda: S.get(AIM["slave"], as_string=True) == "not linked", 12.0,
               lambda: S.describe([AIM["slave"], AIM["slave_raw"]]))
    assert S.get(AIM["slave_raw"], as_string=True) == "4;0;59;0.0000e+00;0.0000e+00;0"
