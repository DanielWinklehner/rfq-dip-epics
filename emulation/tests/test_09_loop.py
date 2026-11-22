"""The control loops (docs/emulation/LOOP.md), without the plant: records in the platform IOC, the
PID in the loop service (container `loop`). The measured value does not follow the actuator
here, so a loop in PID ramps its output at the slew rate and writes every period. What is tested
is the switching and the backstop, not the control (that is test C, `make -C emulation
test-loop`):

- every setting is written and read back, the set point limits clamp the set point;
- a request for PID while a condition is not fulfilled, or while the service does not run, is
  refused with its reason (R5);
- each hand-back from PID with its reason, within its time limit, the request back at MANUAL
  (latch) and the actuator left at its last set point (R4 a to e); the service killed in PID
  (R4 f, the IOC alone);
- a start of the IOC and a start of the service end in MANUAL (R4 g);
- the backstop without the service: a test client in its place writes wrong values, and the
  actuator never gets a value outside the limits, never moves faster than the slew limit, and is
  never written in MANUAL.
The module ends with every loop in MANUAL, the service running, and the devices as they were.

Everything comes from the registry: the loop's roles, and from its database load the PVs of the
measurement (MEAS), the actuator (ACT), the heartbeat (HB), the permit conditions (C1 to C3,
required values R1 to R3, words W1 to W3) and the writer's period (DT)."""
import threading
import time

import epics
import pytest

import system as S
from system import reg
from conftest import restore_writes, snapshot
from test_03_write import write_values

LOOPS = [d for d, dev in reg.devices.items() if dev["class"] == "loop"]
SERVICE = "loop"       # the Compose service of the loop service (run.sh may stop and start it)

# Time limits, seconds from the cause to MANUAL (or to the refusal):
REFUSE_LIMIT = 1.0     # the service reads the request by monitor and decides in its next cycle
                       # (0.2 s), plus Channel Access
PERMIT_LIMIT = {       # the condition's PV changes, then one cycle:
    "interlock": 1.0,  #   interlock box polled every 0.1 s, interlock_open processed with it
    "supply": 2.5,     #   supply output state polled every 1 s (REK STS, TDK OUT?), the switching
}                      #   protocol before it (PRIO HIGH)
MEASUREMENT_LIMIT = 2.0   # REK monitors polled at 10 Hz, reply timeout 150 ms
NODATA_LIMIT = 3.0     # interlock box polled every 0.1 s, libcom1 reply timeout 1 s
OVERRIDE_LIMIT = 1.0   # the actuator's monitor reaches the service at once, then one cycle
NOT_ACCEPTED_LIMIT = 1.0  # a garbled answer fails the set at once, then one cycle
STALE_SLACK = 1.5      # the heartbeat counts once per second, plus one cycle and Channel Access
WATCHDOG_SLACK = 0.5   # service:get scans every 0.1 s, then _dead and _drop by CP links
START_LIMIT = 30.0     # a container up again: the IOC's start, or the service's first contact
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
        self.prefix = self.macros["P"]
        self.meas, self.act, self.hb = (self.macros[k] for k in ("MEAS", "ACT", "HB"))
        self.dt = float(self.macros["DT"])
        self.conditions = [(self.macros["C%d" % n], float(self.macros["R%d" % n]),
                            self.macros["W%d" % n]) for n in (1, 2, 3)]

    def __getitem__(self, role):
        return self.role[role]

    def internal(self, suffix):
        return "%s:%s" % (self.prefix, suffix)

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


def violate(pv):
    if condition_kind(pv) == "interlock":
        sim, signal = door()
        S.sim_set(sim, signal, 0)                  # a door open
    else:
        S.put(reg.role(device_of(pv), "out_cmd"), 0)


def involved(lp):
    """The written PVs the module changes: the loop's, and those of the devices of its
    measurement, actuator and conditions."""
    devices = {lp.device} | {device_of(pv) for pv in [lp.meas, lp.act] +
                             [c for c, _, _ in lp.conditions]}
    return [n for n in reg.writes() if reg.pvs[n]["device"] in devices and n in snapshot]


def service_alive(lp):
    S.wait_for(lambda: S.get(lp["service"]) == 1, START_LIMIT,
               lambda: "the loop service is alive: %s" % S.describe([lp["service"]]))


@pytest.fixture(scope="module", params=LOOPS)
def loop(request):
    lp = Loop(request.param)
    service_alive(lp)
    yield lp
    S.put(lp["mode_cmd"], 0)
    sim, signal = door()
    if (sim, signal) in S.forced:
        S.sim_release(sim, signal)
    if S.field(lp.hb, "DISA") != "0":
        S.put_field(lp.hb, "DISA", 0)
    restore_writes(involved(lp))
    S.wait_for(lambda: S.get(lp["mode"]) == 0, REFUSE_LIMIT, "the loop ends in MANUAL")


def start_value(lp):
    """Inside the output limits, near the minimum: the ramp at the slew rate has room."""
    return S.get(lp["outmin"]) + 1.0


@pytest.fixture
def ready(loop):
    """MANUAL, the service alive, every condition fulfilled, the actuator inside the output
    limits, the measured value away from the set point, so that in PID the output ramps at the
    slew rate and is written every period. Afterwards: MANUAL again."""
    lp = loop
    service_alive(lp)
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
               lambda: "the actuator is written: %s" % S.describe([lp.act, lp["out"]]))


def reason(lp):
    return S.get(lp["reason"], as_string=True)


def expect_hand_back(lp, words, limit, t0):
    """MANUAL within `limit` s of t0 (monotonic), with the reason, the request back at MANUAL,
    and the actuator left at its set point. Returns the seconds it took."""
    S.wait_for(lambda: S.get(lp["mode"]) == 0, limit - (time.monotonic() - t0),
               lambda: "hand-back (%s): %s" % (words, S.describe(
                   [lp["mode"], lp["reason"], lp["pv"], lp.act])))
    took = time.monotonic() - t0
    assert reason(lp) == words, "reason %r, expected %r" % (reason(lp), words)
    assert S.get(lp["mode_cmd"]) == 0, "the request is back at MANUAL (latch)"
    held = S.read(lp.act)
    time.sleep(SETTLE)
    after = S.read(lp.act)
    assert (after["value"], after["timestamp"]) == (held["value"], held["timestamp"]), (
        "the actuator was written after the hand-back: %r then %r" % (held, after))
    assert S.get(lp["mode_cmd"]) == 0 and S.get(lp["mode"]) == 0, "nothing returns to PID"
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


def test_permit_records_show_each_condition(ready):
    for n, (pv, required, words) in enumerate(ready.conditions, 1):
        record = ready["permit%d" % n]
        assert S.get(record) == 0 and S.sevr(record) == S.NO_ALARM, S.describe([record])
        assert S.field(record, "DESC") == words + "?"


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
    assert reason(lp) == words
    assert set(modes) | {S.get(lp["mode"])} == {0}, "the mode stayed MANUAL: %s" % modes
    after = S.read(lp.act)
    assert (after["value"], after["timestamp"]) == (before["value"], before["timestamp"]), (
        "a refused loop wrote the actuator")
    print("%s: refused '%s' after %.2f s" % (lp.device, words, took))


@pytest.mark.parametrize("n", [1, 2, 3])
def test_pid_refused_while_a_permit_is_not_fulfilled(ready, n):
    pv, required, words = ready.conditions[n - 1]
    violate(pv)
    S.wait_for(lambda: S.get(pv) != required, PERMIT_LIMIT[condition_kind(pv)],
               lambda: S.describe([pv]))
    time.sleep(0.5)
    expect_refusal(ready, words)


def test_pid_refused_with_stale_data(ready):
    S.put_field(ready.hb, "DISA", 1)                # the IOC's heartbeat stops counting
    try:
        time.sleep(S.get(ready["stale"]) + STALE_SLACK)
        expect_refusal(ready, "measurement stale")
    finally:
        S.put_field(ready.hb, "DISA", 0)


def test_pid_refused_outside_the_output_limits(ready):
    S.put(ready.act, S.get(ready["outmin"]) - 1.0)
    time.sleep(0.5)
    expect_refusal(ready, "outside output limits")


def test_pid_refused_while_the_service_does_not_run(ready):
    S.container("stop", SERVICE)
    try:
        S.wait_for(lambda: S.get(ready["service"]) == 0, S.get(ready["watchdog"]) + WATCHDOG_SLACK,
                   "service:get 0 after the service stopped")
        assert S.sevr(ready["service"]) == S.MAJOR, "an alarm: %s" % S.describe([ready["service"]])
        expect_refusal(ready, "service stopped")    # cleared by the IOC alone
    finally:
        S.container("start", SERVICE)
    service_alive(ready)


def test_pid_is_accepted_and_bumpless(ready):
    """With every condition fulfilled PID starts, and the first output is the actuator's value."""
    act = S.get(ready.act)
    S.put(ready["mode_cmd"], 1)
    S.wait_for(lambda: S.get(ready["mode"]) == 1, REFUSE_LIMIT, "PID")
    assert reason(ready) == "none"
    # from the actuator's value on, slew limited: at most a few steps of slew x DT so far
    out = S.get(ready["out"])
    assert act <= out <= act + 3 * 0.5 * ready.dt + 1e-6, (act, out)


# --- R4 a to f: hand-back ------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3])
def test_hand_back_when_a_permit_fails(ready, n):
    pv, _, words = ready.conditions[n - 1]
    go_pid(ready)
    t0 = time.monotonic()
    violate(pv)
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
        assert took >= stale - 1.0 - ready.dt, "handed back before the stale time (%.2f s)" % took
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
    set in that window ends INVALID (the answer is not OK), while the next status poll, 1 s
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


def test_hand_back_when_the_service_is_killed(ready):
    """R4 f: the service's container killed (SIGKILL, no clean-up) in PID. The IOC alone sees its
    counter stand still, takes the mode back and raises the alarm."""
    go_pid(ready)
    S.container("kill", SERVICE)
    t0 = time.monotonic()                           # the kill request has returned
    try:
        limit = S.get(ready["watchdog"]) + WATCHDOG_SLACK
        expect_hand_back(ready, "service stopped", limit, t0)
        assert S.get(ready["service"]) == 0 and S.sevr(ready["service"]) == S.MAJOR
    finally:
        S.container("start", SERVICE)
    service_alive(ready)
    S.wait_for(lambda: reason(ready) == "service start", 5.0, "the service's start")
    assert S.get(ready["mode"]) == 0


# --- R4 g: starts ----------------------------------------------------------------------------------

def test_restart_of_the_service_starts_in_manual(ready):
    go_pid(ready)
    S.container("restart", SERVICE)                # SIGTERM: the service leaves MANUAL itself
    service_alive(ready)
    S.wait_for(lambda: reason(ready) == "service start", 5.0,
               lambda: "after the start: %s" % S.describe([ready["reason"]]))
    assert S.get(ready["mode"]) == 0 and S.get(ready["mode_cmd"]) == 0


def test_restart_of_the_ioc_starts_in_manual(ready):
    ioc = reg.devices[ready.device]["ioc"]
    hb = reg.iocs[ioc]["roles"]["heartbeat"]
    go_pid(ready)
    settings = {pv: S.get(pv) for pv in ready.settings()}
    S.container("restart", S.ioc_container(ioc))
    S.wait_for(lambda: S.connected(hb) and S.get(hb) >= 1, START_LIMIT, "IOC back")
    assert S.get(ready["mode"]) == 0 and S.get(ready["mode_cmd"]) == 0, "MANUAL after the start"
    assert reason(ready) == "IOC start"
    assert {pv: S.get(pv) for pv in settings} == settings, "settings kept (autosave)"
    service_alive(ready)
    time.sleep(1.0)
    assert reason(ready) == "IOC start", "the service leaves the reason of the IOC's start"
    # past the supplies' first contact (GRACE), then PID works again
    gates = [g for g in (reg.gate_record(d) for d in reg.devices) if g and reg.pvs[g]["ioc"] == ioc]
    S.wait_for(lambda: all(S.field(g, "DISA") == "0" for g in gates), START_LIMIT, "gates enabled")
    for pv, required, _ in ready.conditions:
        fulfil(pv, required)
    S.put(ready.act, start_value(ready))
    time.sleep(1.5)
    go_pid(ready)


# --- the backstop, without the service -------------------------------------------------------------

class FakeService:
    """In the service's place: counts _count (so that the IOC sees it alive), sets _active and
    writes _out as told."""

    def __init__(self, lp):
        self.lp = lp
        self.stop = threading.Event()
        self.counting = True
        self.thread = threading.Thread(target=self._count, daemon=True)

    def _count(self):
        count = 0
        pv = epics.PV(self.lp.internal("_count"))
        while not self.stop.wait(0.1):
            if self.counting:
                count += 1
                pv.put(count, wait=False)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()
        S.put(self.lp.internal("_active"), 0)

    def out(self, value):
        S.put(self.lp.internal("_out"), value)


@pytest.fixture
def backstop(ready):
    """The service stopped and the test client in its place; the actuator's monitor records every
    value it gets."""
    S.container("stop", SERVICE)
    events = []
    act = epics.PV(ready.act, form="time", auto_monitor=True,
                   callback=lambda value=None, timestamp=None, **kw: events.append((timestamp, value)))
    act.wait_for_connection(5.0)
    try:
        with FakeService(ready) as fake:
            S.wait_for(lambda: S.get(ready["service"]) == 1, 2.0, "the client counts: alive")
            yield ready, fake, events
    finally:
        act.clear_callbacks()
        S.container("start", SERVICE)
        service_alive(ready)


def written(events, since):
    return [(t, v) for t, v in events if t is not None and t >= since]


def test_backstop_limits_and_slew(backstop):
    lp, fake, events = backstop
    lo, hi, slew = (S.get(lp[r]) for r in ("outmin", "outmax", "slew"))
    fake.out(S.get(lp.act))
    S.put(lp["mode_cmd"], 1)
    S.put(lp.internal("_active"), 1)
    S.wait_for(lambda: S.get(lp["mode"]) == 1, 1.0, "PID with the client")
    t0 = time.time()
    for target in (hi + 50.0, lo - 50.0, hi + 50.0, 1e6, -1e6, hi + 50.0):
        fake.out(target)
        time.sleep(1.5)
    S.put(lp["mode_cmd"], 0)
    got = written(events, t0)
    assert len(got) >= 10, "the actuator was written: %s" % got
    values = [v for _, v in got]
    assert all(lo - 1e-9 <= v <= hi + 1e-9 for v in values), "outside [%g, %g]: %s" % (lo, hi, values)
    steps = [abs(b - a) for a, b in zip(values, values[1:])]
    assert max(steps) <= slew * lp.dt + 1e-9, "a step above slew x DT = %g: %g" % (
        slew * lp.dt, max(steps))
    print("%s: backstop: %d writes within [%g, %g], largest step %.3f (slew x DT %.3f)" % (
        lp.device, len(got), lo, hi, max(steps), slew * lp.dt))


def test_backstop_never_writes_in_manual(backstop):
    lp, fake, events = backstop
    t0 = time.time()
    S.put(lp.internal("_active"), 1)                # accepted, but not requested
    for target in (S.get(lp.act) + 3.0, S.get(lp.act) - 3.0):
        fake.out(target)
        time.sleep(1.0)
    S.put(lp["mode_cmd"], 1)                         # requested, but not accepted
    S.put(lp.internal("_active"), 0)
    fake.out(S.get(lp.act) + 3.0)
    time.sleep(1.0)
    assert S.get(lp["mode"]) == 0
    assert written(events, t0) == [], "written in MANUAL: %s" % written(events, t0)
    S.put(lp["mode_cmd"], 0)


def test_backstop_never_writes_from_outside_the_limits(backstop):
    """An actuator standing outside the output limits is not moved by the loop at all."""
    lp, fake, events = backstop
    S.put(lp.act, S.get(lp["outmin"]) - 5.0)
    t0 = time.time()
    S.put(lp["mode_cmd"], 1)
    S.put(lp.internal("_active"), 1)
    fake.out(S.get(lp["outmax"]))
    time.sleep(1.5)
    assert S.get(lp["mode"]) == 1
    assert written(events, t0) == [], written(events, t0)
    S.put(lp["mode_cmd"], 0)


def test_backstop_takes_the_mode_back_when_the_client_stops_counting(backstop):
    lp, fake, events = backstop
    fake.out(S.get(lp.act))
    S.put(lp["mode_cmd"], 1)
    S.put(lp.internal("_active"), 1)
    S.wait_for(lambda: S.get(lp["mode"]) == 1, 1.0, "PID with the client")
    t0 = time.monotonic()
    fake.counting = False
    expect_hand_back(lp, "service stopped", S.get(lp["watchdog"]) + WATCHDOG_SLACK, t0)
    assert S.sevr(lp["service"]) == S.MAJOR


def test_backstop_stops_writing_after_someone_else_wrote(backstop):
    """In PID, with the client still asking for more, an operator's write to the actuator is not
    overwritten: the writer writes only while the actuator holds its own last value."""
    lp, fake, events = backstop
    fake.out(S.get(lp["outmax"]))
    S.put(lp["mode_cmd"], 1)
    S.put(lp.internal("_active"), 1)
    S.wait_for(lambda: S.get(lp["mode"]) == 1, 1.0, "PID with the client")
    time.sleep(1.0)
    assert len(written(events, 0)) > 0, "the writer writes"
    value = S.get(lp["outmin"]) + 0.5
    S.put(lp.act, value)
    t0 = time.time()
    time.sleep(1.5)
    assert S.get(lp.act) == value
    assert [v for _, v in written(events, t0)] == [], "written after the operator"
    S.put(lp["mode_cmd"], 0)
