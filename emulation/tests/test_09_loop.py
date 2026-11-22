"""The control loops of the loop IOC (docs/emulation/LOOP.md), without the plant: the measured value
does not follow the actuator here, so a loop in PID ramps its output at the slew rate. What is
tested is the switching, not the control (that is test C, `make -C emulation test-loop`):

- every setting is written and read back, the set point limits clamp the set point;
- a request for PID while a condition is not fulfilled is refused, with its reason (R5);
- each hand-back from PID, with its reason, within its time limit, the request back at MANUAL
  (latch) and the actuator left at its last set point (R4 a to e);
- a restart of the loop IOC in PID starts in MANUAL, reason "IOC start", settings kept (R4 f);
- the platform IOC's container stopped and started: hand-back, the loop IOC keeps running, it
  reconnects, PID works again.
The module ends with every loop in MANUAL and its devices as they were.

Everything comes from the registry: the loop's roles, and from its database load the PVs of the
measurement (MEAS), the actuator (ACT), the heartbeat (HB) and the permit conditions (C1 to C3,
required values R1 to R3, words W1 to W3)."""
import time

import pytest

import system as S
from system import reg
from conftest import restore_writes, snapshot
from test_03_write import write_values

LOOPS = [d for d, dev in reg.devices.items() if dev["class"] == "loop"]
PERIOD = 0.2           # s, SCAN of the loop (macro SCAN)

# Time limits, seconds from the cause to MANUAL (or to the refusal):
REFUSE_LIMIT = 1.0     # the request is read once per period (0.2 s), plus Channel Access
PERMIT_LIMIT = {       # the condition's PV changes, then one loop period:
    "interlock": 1.0,  #   interlock box polled every 0.1 s, interlock_open processed with it
    "supply": 2.5,     #   supply output state polled every 1 s (REK STS, TDK OUT?), the switching
}                      #   protocol before it (PRIO HIGH)
MEASUREMENT_LIMIT = 2.0  # REK monitors polled at 10 Hz, reply timeout 150 ms
NODATA_LIMIT = 3.0     # interlock box polled every 0.1 s, libcom1 reply timeout 1 s
OVERRIDE_LIMIT = 1.0   # the actuator's monitor reaches the mirror at once, then one period
NOT_ACCEPTED_LIMIT = 1.0  # a garbled answer fails the set at once, then one period
# docker stop: the container's network goes with it, and the loop IOC's Channel Access client
# does not learn that the circuit is closed until its own echo timeout (tens of seconds). The
# heartbeat stops at once, so the loop hands back as stale: within the stale time plus
# STALE_SLACK (or earlier as "measurement no data", should the disconnect be seen first).
RECONNECT_LIMIT = 30.0    # the platform IOC up again: its beacons, then CA reconnects the links
STALE_SLACK = 1.5      # the heartbeat counts once per second, plus one period and Channel Access
SETTLE = 1.0           # s the actuator is watched after a hand-back: it must not change
GARBLED = 0.5          # s of garbled answers for "set not accepted" (between two status polls 1 s
                       # apart). Not silence: sets would wait behind polls that time out (300 ms
                       # each) and be answered after the fault


class Loop:
    def __init__(self, device):
        dev = reg.devices[device]
        self.device = device
        self.role = dev["roles"]
        self.macros = dev["loads"][0]["macros"]
        self.meas, self.act, self.hb = (self.macros[k] for k in ("MEAS", "ACT", "HB"))
        self.conditions = [(self.macros["C%d" % n], float(self.macros["R%d" % n]),
                            self.macros["W%d" % n]) for n in (1, 2, 3)]
        self.words = reg.pvs[self.role["reason"]]["states"]

    def __getitem__(self, role):
        return self.role[role]

    def settings(self):
        return [pv for pv in self.role.values() if reg.pvs[pv]["access"] == "w"
                and reg.pvs[pv].get("readback") is None]


def device_of(pv):
    return reg.pvs[pv]["device"]


def condition_kind(pv):
    """'interlock' (a permit of the interlock box) or 'supply' (an output state)."""
    return "interlock" if reg.devices[device_of(pv)]["class"] == "interlock" else "supply"


def door():
    """The interlock simulator and the signal of its first door switch (test_06)."""
    ilk = next(d for d, dev in reg.devices.items() if dev["class"] == "interlock")
    return reg.devices[ilk]["simulators"][0], sorted(reg.devices[ilk]["channels"])[0]


def fulfil(pv, required):
    if condition_kind(pv) == "interlock":
        sim, signal = door()
        if (sim, signal) in S.forced:
            S.sim_release(sim, signal)
    else:
        S.put(reg.role(device_of(pv), "out_cmd"), int(required))
    S.wait_for(lambda: S.get(pv) == required and S.sevr(pv) != S.INVALID, 5.0,
               lambda: "condition fulfilled: %s" % S.describe([pv]))


def violate(pv, required):
    if condition_kind(pv) == "interlock":
        sim, signal = door()
        S.sim_set(sim, signal, 0)                  # a door open
    else:
        S.put(reg.role(device_of(pv), "out_cmd"), 0)


def involved(loop):
    """The written PVs the module changes: the loop's, and those of the devices of its
    measurement, actuator and conditions."""
    devices = {loop.device} | {device_of(pv) for pv in [loop.meas, loop.act] +
                                [c for c, _, _ in loop.conditions]}
    return [n for n in reg.writes() if reg.pvs[n]["device"] in devices and n in snapshot]


@pytest.fixture(scope="module", params=LOOPS)
def loop(request):
    lp = Loop(request.param)
    yield lp
    S.put(lp["mode_cmd"], 0)
    sim, signal = door()
    if (sim, signal) in S.forced:
        S.sim_release(sim, signal)
    hb = lp.hb
    if S.field(hb, "DISA") != "0":
        S.put_field(hb, "DISA", 0)
    restore_writes(involved(lp))
    S.wait_for(lambda: S.get(lp["mode"]) == 0, REFUSE_LIMIT, "the loop ends in MANUAL")


def start_value(lp):
    """Inside the output limits, near the minimum: the ramp at the slew rate has room."""
    return S.get(lp["outmin"]) + 1.0


@pytest.fixture
def ready(loop):
    """MANUAL, every condition fulfilled, the actuator inside the output limits, the measured
    value away from the set point, so that in PID the output ramps at the slew rate and the loop
    writes every period. Afterwards: MANUAL again, the conditions fulfilled."""
    lp = loop
    S.put(lp["mode_cmd"], 0)
    S.wait_for(lambda: S.get(lp["mode"]) == 0, REFUSE_LIMIT, "MANUAL")
    if S.field(lp.hb, "DISA") != "0":
        S.put_field(lp.hb, "DISA", 0)
    for pv, required, _ in lp.conditions:
        fulfil(pv, required)
    S.put(lp["slew"], 0.5)                          # 0.1 per period: a write every period
    S.put(lp["sp"], write_values(lp["sp"])[1])
    S.put(lp.act, start_value(lp))
    S.wait_for(lambda: S.get(lp["pv"]) != S.get(lp["sp"]) and S.sevr(lp["pv"]) != S.INVALID,
               5.0, lambda: "measured value valid: %s" % S.describe([lp["pv"]]))
    S.wait_for(lambda: S.get(lp["out"]) == S.get(lp.act), 2.0,
               lambda: "MANUAL follows the actuator: %s" % S.describe([lp["out"], lp.act]))
    S.wait_for(lambda: S.sevr(lp.hb) != S.INVALID and S.get(lp.hb) > 0, 5.0, "heartbeat")
    time.sleep(1.5)                                 # a heartbeat change seen: not stale
    yield lp
    S.put(lp["mode_cmd"], 0)
    S.wait_for(lambda: S.get(lp["mode"]) == 0, REFUSE_LIMIT, "MANUAL after the test")


def go_pid(lp):
    before = S.get(lp.act)
    S.put(lp["mode_cmd"], 1)
    S.wait_for(lambda: S.get(lp["mode"]) == 1, REFUSE_LIMIT,
               lambda: "PID: %s" % S.describe([lp["mode"], lp["mode_cmd"], lp["reason"]]))
    S.wait_for(lambda: S.get(lp.act) != before, 2.0,
               lambda: "the loop writes the actuator: %s" % S.describe([lp.act, lp["out"]]))


def expect_hand_back(lp, words, limit, t0):
    """MANUAL within `limit` s of t0 (monotonic), with the reason, the request back at MANUAL,
    and the actuator left at its set point. Returns the seconds it took."""
    S.wait_for(lambda: S.get(lp["mode"]) == 0, limit - (time.monotonic() - t0),
               lambda: "hand-back (%s): %s" % (words, S.describe(
                   [lp["mode"], lp["reason"], lp["pv"], lp.act])))
    took = time.monotonic() - t0
    reason = S.get(lp["reason"], as_string=True)
    assert reason == words, "reason %r, expected %r" % (reason, words)
    assert S.get(lp["mode_cmd"]) == 0, "the request is back at MANUAL (latch)"
    held = S.read(lp.act)
    time.sleep(SETTLE)
    after = S.read(lp.act)
    assert (after["value"], after["timestamp"]) == (held["value"], held["timestamp"]), (
        "the actuator was written after the hand-back: %r then %r" % (held, after))
    S.wait_for(lambda: S.get(lp["mode_cmd"]) == 0 and S.get(lp["mode"]) == 0, PERIOD * 3,
               "nothing returns to PID by itself")
    print("%s: hand-back '%s' after %.2f s" % (lp.device, words, took))
    return took


# --- registry, settings ------------------------------------------------------------------------

def test_generic_write_tests_never_request_pid(loop):
    """test_03 writes every written PV of the registry inside its test range: for the mode
    request that range holds only MANUAL."""
    assert write_values(loop["mode_cmd"]) == [0]


def test_every_setting_is_written_and_read_back(loop):
    for pv in loop.settings():
        old = S.get(pv)
        try:
            for value in write_values(pv):
                S.put(pv, value)
                assert S.get(pv) == pytest.approx(value), S.describe([pv])
                assert S.sevr(pv) == S.NO_ALARM, S.describe([pv])
        finally:
            S.put(pv, old)


def test_set_point_limits_clamp_the_set_point(loop):
    sp = loop["sp"]
    old = {f: float(S.field(sp, f)) for f in ("DRVL", "DRVH")}
    value = S.get(sp)
    try:
        S.put_field(sp, "DRVH", 15.0)
        S.put_field(sp, "DRVL", 5.0)
        assert float(S.field(sp, "DRVH")) == 15.0 and float(S.field(sp, "DRVL")) == 5.0
        S.put(sp, 30.0)
        assert S.get(sp) == 15.0, "above the maximum: clamped to it"
        S.put(sp, 1.0)
        assert S.get(sp) == 5.0, "below the minimum: clamped to it"
    finally:
        S.put_field(sp, "DRVL", old["DRVL"])
        S.put_field(sp, "DRVH", old["DRVH"])
        S.put(sp, value)


# --- R5: refusal ---------------------------------------------------------------------------------

def expect_refusal(lp, words):
    t0 = time.monotonic()
    before = S.read(lp.act)
    modes = []
    S.put(lp["mode_cmd"], 1)

    def refused():
        modes.append(S.get(lp["mode"]))
        return S.get(lp["mode_cmd"]) == 0
    S.wait_for(refused, REFUSE_LIMIT, lambda: "refused: %s" % S.describe([lp["mode_cmd"], lp["reason"]]),
               interval=0.02)
    took = time.monotonic() - t0
    assert S.get(lp["reason"], as_string=True) == words
    assert set(modes) | {S.get(lp["mode"])} == {0}, "the mode stayed MANUAL: %s" % modes
    after = S.read(lp.act)
    assert (after["value"], after["timestamp"]) == (before["value"], before["timestamp"]), (
        "a refused loop wrote the actuator")
    print("%s: refused '%s' after %.2f s" % (lp.device, words, took))


@pytest.mark.parametrize("n", [1, 2, 3])
def test_pid_refused_while_a_permit_is_not_fulfilled(ready, n):
    pv, required, words = ready.conditions[n - 1]
    violate(pv, required)
    S.wait_for(lambda: S.get(pv) != required, PERMIT_LIMIT[condition_kind(pv)],
               lambda: S.describe([pv]))
    time.sleep(PERIOD * 2)
    expect_refusal(ready, words)


def test_pid_refused_with_stale_data(ready):
    S.put_field(ready.hb, "DISA", 1)                # the owner's heartbeat stops counting
    try:
        time.sleep(S.get(ready["stale"]) + STALE_SLACK)
        expect_refusal(ready, "measurement stale")
    finally:
        S.put_field(ready.hb, "DISA", 0)


def test_pid_refused_outside_the_output_limits(ready):
    S.put(ready.act, S.get(ready["outmin"]) - 1.0)
    time.sleep(PERIOD * 2)
    expect_refusal(ready, "outside output limits")


def test_pid_is_accepted_and_bumpless(ready):
    """With every condition fulfilled PID starts, and the first output is the actuator's value."""
    act = S.get(ready.act)
    S.put(ready["mode_cmd"], 1)
    S.wait_for(lambda: S.get(ready["mode"]) == 1, REFUSE_LIMIT, "PID")
    assert S.get(ready["reason"], as_string=True) == "none"
    # the ramp is slew limited from the actuator's value on: the first values are act + k slew dt
    out = S.get(ready["out"])
    assert act <= out <= act + 3 * 0.5 * PERIOD + 1e-6, (act, out)


# --- R4 a to e: hand-back ------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3])
def test_hand_back_when_a_permit_fails(ready, n):
    pv, required, words = ready.conditions[n - 1]
    go_pid(ready)
    t0 = time.monotonic()
    violate(pv, required)
    expect_hand_back(ready, words, PERMIT_LIMIT[condition_kind(pv)], t0)


def test_hand_back_when_the_measurement_is_invalid(ready):
    sim, unit = reg.sim_of(reg.role(device_of(ready.meas), "vset"))
    go_pid(ready)
    with S.fault(sim, "silent", unit) as f:
        expect_hand_back(ready, "measurement no data", MEASUREMENT_LIMIT, f.t0)
    S.wait_for(lambda: S.sevr(ready["pv"]) != S.INVALID, 20.0, "measurement back")


def test_hand_back_when_a_permit_has_no_data(ready):
    pv, _, _ = ready.conditions[0]
    sim = reg.devices[device_of(pv)]["simulators"][0]
    go_pid(ready)
    with S.fault(sim, "silent") as f:
        expect_hand_back(ready, "permit 1 no data", NODATA_LIMIT, f.t0)
    S.wait_for(lambda: S.sevr(pv) != S.INVALID, 20.0, "permit 1 back")


def test_hand_back_when_the_data_is_stale(ready):
    go_pid(ready)
    stale = S.get(ready["stale"])
    t0 = time.monotonic()
    S.put_field(ready.hb, "DISA", 1)
    try:
        took = expect_hand_back(ready, "measurement stale", stale + STALE_SLACK, t0)
        assert took >= stale - 1.0 - PERIOD, "handed back before the stale time (%.2f s)" % took
    finally:
        S.put_field(ready.hb, "DISA", 0)


def test_hand_back_when_someone_else_writes_the_actuator(ready):
    go_pid(ready)
    t0 = time.monotonic()
    value = start_value(ready) + 0.5
    S.put(ready.act, value)
    expect_hand_back(ready, "written by someone else", OVERRIDE_LIMIT, t0)
    assert S.get(ready.act) == value, "the operator's value stays"


def test_hand_back_when_the_actuator_does_not_accept_a_set(ready):
    """The actuator's simulator garbles its answers for GARBLED s right after a status poll: the
    loop's set in that window ends INVALID (the answer is not OK), while the next status poll, 1 s
    later, is answered."""
    act_dev = device_of(ready.act)
    sim = reg.devices[act_dev]["simulators"][0]
    state = reg.role(act_dev, "out_state")
    go_pid(ready)
    stamp = S.read(state)["timestamp"]
    S.wait_for(lambda: S.read(state)["timestamp"] > stamp, 2.0, "a status poll", interval=0.02)
    t0 = time.monotonic()
    S.control(sim).fault("garbage", duration=GARBLED)
    try:
        expect_hand_back(ready, "set not accepted", NOT_ACCEPTED_LIMIT, t0)
        assert S.sevr(ready.act) == S.INVALID
    finally:
        S.control(sim).clear("garbage")
        S.put(ready.act, start_value(ready))       # valid again: the operator writes it
    assert S.sevr(ready.act) == S.NO_ALARM


# --- R4 f, and the platform IOC stopped ------------------------------------------------------------

def ioc_of(lp):
    return reg.devices[lp.device]["ioc"]


def test_restart_of_the_loop_ioc_starts_in_manual(ready):
    go_pid(ready)
    settings = {pv: S.get(pv) for pv in ready.settings()}
    S.container("restart", S.ioc_container(ioc_of(ready)))
    hb = reg.iocs[ioc_of(ready)]["roles"]["heartbeat"]
    S.wait_for(lambda: S.connected(hb) and S.get(hb) >= 1, 30.0, "loop IOC back")
    held = S.read(ready.act)
    assert S.get(ready["mode"]) == 0, "MANUAL after the start"
    assert S.get(ready["mode_cmd"]) == 0
    assert S.get(ready["reason"], as_string=True) == "IOC start"
    time.sleep(SETTLE)
    after = S.read(ready.act)
    assert (after["value"], after["timestamp"]) == (held["value"], held["timestamp"])
    assert {pv: S.get(pv) for pv in settings} == settings, "settings kept (autosave)"


def test_platform_ioc_stopped_and_started(ready):
    """docker stop of the container of the IOC that owns the measurement: hand-back (stale data,
    see above), the loop IOC keeps running; docker start: the loop reconnects and PID works
    again."""
    owner = reg.pvs[ready.meas]["ioc"]
    loop_hb = reg.iocs[ioc_of(ready)]["roles"]["heartbeat"]
    go_pid(ready)
    t0 = time.monotonic()
    S.container("stop", S.ioc_container(owner))
    try:
        limit = S.get(ready["stale"]) + STALE_SLACK
        S.wait_for(lambda: S.get(ready["mode"]) == 0, limit - (time.monotonic() - t0),
                   lambda: "hand-back: %s" % S.describe([ready["mode"], ready["reason"]]))
        took = time.monotonic() - t0
        reason = S.get(ready["reason"], as_string=True)
        assert reason in ("measurement stale", "measurement no data"), reason
        assert S.get(ready["mode_cmd"]) == 0
        count = S.get(loop_hb)
        time.sleep(2.0)
        assert S.get(loop_hb) > count, "the loop IOC keeps running"
        print("%s: hand-back '%s' %.2f s after docker stop of %s began" % (
            ready.device, reason, took, owner))
    finally:
        S.container("start", S.ioc_container(owner))
    hb = reg.iocs[owner]["roles"]["heartbeat"]
    took = S.wait_for(lambda: S.connected(hb) and S.sevr(ready["pv"]) != S.INVALID, RECONNECT_LIMIT,
                      lambda: "reconnected: %s" % S.describe([ready["pv"], hb]))
    print("%s: measurement valid again %.1f s after docker start" % (ready.device, took))
    # the platform IOC past its first contact (GRACE), then every condition back: PID again
    gates = [g for g in (reg.gate_record(d) for d in reg.devices) if g and reg.pvs[g]["ioc"] == owner]
    S.wait_for(lambda: all(S.field(g, "DISA") == "0" for g in gates), 30.0, "gates enabled")
    for pv, required, _ in ready.conditions:
        fulfil(pv, required)
    S.put(ready.act, start_value(ready))
    time.sleep(1.5)
    go_pid(ready)
