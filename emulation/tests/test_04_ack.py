"""Acknowledgement: a set the registry marks as acknowledged ends in an alarm on the set record
when its simulator is silent, and once the fault is cleared the device has NOT executed it. The
Matsusada sets carry no acknowledgement (the CO series does not answer a set); for them the test
proves what the design promises instead: the set-point echo turns INVALID."""
import time

import pytest

import system as S
from system import reg
from conftest import baseline_ok, write_target
from test_03_write import (ECHO_LIMIT, MEASURED, RECOVER_LIMIT, WRITES, OutputOn, device_pvs, is_switch,
                           tolerance)

ACKED = [n for n in WRITES if reg.pvs[n]["ack"]]
ECHOED = [n for n in WRITES if not reg.pvs[n]["ack"]]       # Matsusada: echo instead of answer
# A silent device: the set waits for its reply timeout (StreamDevice ReplyTimeout: 150 ms to 1 s
# in the protocol files), then the record is INVALID. The echo of a Matsusada set is read by a
# forward link right after the set: INVALID within ECHO_LIMIT.


def new_value(name):
    """A value inside the test range that differs from what the device has now."""
    spec = reg.pvs[name]
    lo, hi = spec["test"]
    rb = spec.get("readback")
    now = S.get(rb) if rb else S.get(name)
    if is_switch(name):
        return 1 - int(round(now))
    for f in (0.53, 0.29, 0.81):
        v = lo + f * (hi - lo)
        if abs(v - now) > 3 * tolerance(name):
            return v
    raise AssertionError("no test value away from %r" % now)


def unacknowledged(name, acked):
    spec = reg.pvs[name]
    device = spec["device"]
    rb = spec.get("readback")
    sim, unit = reg.sim_of(name)
    assert sim, "%s names no simulator (sim)" % name
    others = [n for n in device_pvs(device) if n not in (name, rb)]
    S.wait_for(lambda: baseline_ok(device_pvs(device)), RECOVER_LIMIT,
               lambda: "%s before the test: %s" % (device, S.describe(device_pvs(device))))
    try:
        with OutputOn(name):
            before = S.get(rb) if rb else None
            value = new_value(name)
            with S.fault(sim, "silent", unit):
                S.put(name, value)
                if acked:
                    assert S.sevr(name) == S.INVALID, (
                        "a set to a silent device ends without alarm: %s" % S.describe([name]))
                else:
                    S.wait_for(lambda: S.sevr(rb) == S.INVALID, ECHO_LIMIT,
                               lambda: "echo INVALID after a set to a silent supply: %s"
                               % S.describe([rb, name]))
            # cleared: the device answers again; read the read-back fresh (it may be passive)
            S.wait_for(lambda: baseline_ok(scanned(others)), RECOVER_LIMIT,
                       lambda: "%s recovers: %s" % (device, S.describe(scanned(others))))
            if rb:
                S.put_field(rb, "PROC", 1)
                S.wait_for(lambda: S.sevr(rb) != S.INVALID, ECHO_LIMIT,
                           lambda: "read-back valid again: %s" % S.describe([rb]))
                assert abs(S.get(rb) - before) <= tolerance(name), (
                    "the silent device executed the set: %s was %r, set %r" % (
                        S.describe([rb]), before, value))
            # without a read-back the other PVs of the device show it (AIM:enable := 0 would
            # switch the gauge off and turn the pressure INVALID): baseline_ok above
    finally:
        t_restore = time.time()
        S.put(name, write_target(name))
    if rb and reg.pvs[rb].get("role") not in MEASURED:
        S.wait_fresh(rb, t_restore, lambda v: abs(v - write_target(name)) <= tolerance(name),
                     ECHO_LIMIT, "read-back of the restored %s" % name)
    assert S.sevr(name) == S.NO_ALARM, "after the fault: %s" % S.describe([name])
    # the restoring write is followed by its echo and switching records (forward links that run
    # after the caput has returned): the whole device is back before the next test faults it
    S.wait_for(lambda: baseline_ok(device_pvs(device)), RECOVER_LIMIT,
               lambda: "%s after the test: %s" % (device, S.describe(device_pvs(device))))


_scan = {}


def scanned(names):
    """The PVs of a list that are processed periodically. A passive record (ToggleOutput, an echo
    of a supply that is not polled) keeps the alarm of the failed write until the next write."""
    for n in names:
        if n not in _scan:
            _scan[n] = S.field(n, "SCAN")
    return [n for n in names if _scan[n] != "Passive"]


@pytest.mark.parametrize("name", ACKED)
def test_acknowledged_set_to_silent_device_alarms_and_is_not_executed(name):
    unacknowledged(name, True)


@pytest.mark.parametrize("name", ECHOED)
def test_unanswered_set_turns_its_echo_invalid_and_is_not_executed(name):
    unacknowledged(name, False)
