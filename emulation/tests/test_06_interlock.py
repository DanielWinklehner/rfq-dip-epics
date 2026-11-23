"""Across the two IOCs: an open interlock door (old interlock box, rack IOC) forces off the
outputs of every supply gated by the permit, the AU supplies on the rack IOC and the filament
discharge supply on the platform IOC (through a Channel Access link), and clears their requests.
The permit latches (owner's decision, 2026-11-21): a request made while the door is open is
cleared at once, and when the door closes nothing switches on by itself; the operator switches on
again, and that works. While the door is open the output is kept off as a state (P45): a client
that writes a supply's switching record ToggleOutput directly (P28) switches it on for a moment,
and _permit:enforce switches it off again and counts it. "All HV off" switches all AU supplies
off and clears their requests."""
import time

import pytest

import system as S
from system import reg

ILK = "ilk_old"
PERMIT = reg.role(ILK, "open")
INTERLOCK_SIM = reg.devices[ILK]["simulators"][0]
DOOR = sorted(reg.devices[ILK]["channels"])[0]          # i1: a door switch, signal of the same name
SWITCH_LIMIT = 3.0     # permit -> output: OutputIntlk follows the permit by a CP link (and scans
                       # every 1 s); the switching protocol is sent at once (PRIO HIGH)
SETTLED = 2            # processings of each gate record after the door closed, before the
                       # outputs are checked to have stayed off (it scans every 1 s)
ENFORCE_LIMIT = 5.0    # a direct write of ToggleOutput while the permit is lost -> output off
                       # again: the read-back of SW? (its forward link), two evaluations of
                       # _permit:enforce (scans every 1 s; two more when the periodic read of SW?
                       # every 5 s breaks the row, matsusada_au20p7.db), the off sequence


def gated():
    """Devices whose output the permit gates: an output request and a gate record."""
    return [d for d in reg.devices if reg.has_role(d, "out_cmd") and reg.gate_record(d)]


GATED = gated()
ALLOFF_DEV = next(d for d, dev in reg.devices.items() if dev["class"] == "command")
ALLOFF = reg.role(ALLOFF_DEV, "cmd")
ALLOFF_SUPPLIES = [d for d in reg.devices if d != ALLOFF_DEV and any(
    s.split(":")[0] in reg.devices[ALLOFF_DEV]["simulators"] and ":" in s
    for s in reg.devices[d]["simulators"])]


def direct(device, record):
    """A record of a gated supply beside its gate (ToggleOutput, _permit:enforce): internal, no
    role; named from the gate record's prefix and found in the registry."""
    name = reg.gate_record(device).rsplit(":", 1)[0] + ":" + record
    assert name in reg.devices[device]["pvs"], name
    return name


def output_on(device):
    """The supply's real output: simulator signal <unit>.output."""
    sim, unit = reg.devices[device]["simulators"][0].split(":")
    return S.sim_value(sim, "%s.output" % unit) == 1.0


def outputs(devices):
    return {d: output_on(d) for d in devices}


def requests(devices):
    return {d: S.get(reg.role(d, "out_cmd")) for d in devices}


def switch_all_on(devices):
    for d in devices:
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: all(outputs(devices).values()), SWITCH_LIMIT,
               lambda: "outputs on: %s" % outputs(devices))


def gates_processed(since, times):
    """Every gate record processed `times` times after `since` (wall clock): its time stamp
    is at least times-1 scan periods (1 s) past since."""
    return all(S.read(reg.gate_record(d))["timestamp"] > since + times - 1 for d in GATED)


@pytest.fixture
def everything_off():
    yield
    if (INTERLOCK_SIM, DOOR) in S.forced:
        S.sim_release(INTERLOCK_SIM, DOOR)
    S.wait_for(lambda: S.get(PERMIT) == 0, SWITCH_LIMIT, lambda: S.describe([PERMIT]))
    for d in GATED:
        S.put(reg.role(d, "out_cmd"), 0)
    S.wait_for(lambda: not any(outputs(GATED).values()), SWITCH_LIMIT,
               lambda: "outputs off after the test: %s" % outputs(GATED))


def test_registry_has_the_gated_supplies():
    assert len(GATED) == 5, GATED              # four AU supplies, the REK
    assert {reg.devices[d]["ioc"] for d in GATED} == set(reg.iocs)   # both IOCs
    assert len(ALLOFF_SUPPLIES) == 4, ALLOFF_SUPPLIES


def test_open_door_switches_off_and_latches(everything_off):
    switch_all_on(GATED)
    S.sim_set(INTERLOCK_SIM, DOOR, 0)                     # door open
    S.wait_for(lambda: S.get(PERMIT) == 1, SWITCH_LIMIT, lambda: S.describe([PERMIT]))
    S.wait_for(lambda: not any(outputs(GATED).values()), SWITCH_LIMIT,
               lambda: "outputs forced off by the open door: %s" % outputs(GATED))
    S.wait_for(lambda: not any(requests(GATED).values()), SWITCH_LIMIT,
               lambda: "requests cleared by the open door: %s" % requests(GATED))
    for d in GATED:
        st = reg.role(d, "status")
        S.wait_for(lambda: S.get(st) == 0, SWITCH_LIMIT, lambda: S.describe([st]))
    # a request while the door is open is cleared at once and switches nothing
    for d in GATED:
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: not any(requests(GATED).values()), SWITCH_LIMIT,
               lambda: "requests made while the door is open, cleared: %s" % requests(GATED))
    assert not any(outputs(GATED).values()), outputs(GATED)
    # a direct write of the switching record while the door is open (P28): on for a moment, off
    # again by _permit:enforce, which counts it (P45)
    counts = {d: S.get(direct(d, "_permit:enforce")) for d in GATED}
    t0 = time.monotonic()
    for d in GATED:
        S.put(direct(d, "ToggleOutput"), 1)
    S.wait_for(lambda: all(outputs(GATED).values()), 1.0,
               lambda: "outputs on by a direct write: %s" % outputs(GATED))
    S.wait_for(lambda: not any(outputs(GATED).values()), ENFORCE_LIMIT - (time.monotonic() - t0),
               lambda: "outputs off again while the door is open: %s" % outputs(GATED))
    after = {d: S.get(direct(d, "_permit:enforce")) for d in GATED}
    assert after == {d: n + 1 for d, n in counts.items()}, (counts, after)
    assert not any(requests(GATED).values()), requests(GATED)
    S.sim_set(INTERLOCK_SIM, DOOR, 1)                     # door closed
    S.sim_release(INTERLOCK_SIM, DOOR)
    S.wait_for(lambda: S.get(PERMIT) == 0, SWITCH_LIMIT, lambda: S.describe([PERMIT]))
    closed = time.time()
    S.wait_for(lambda: gates_processed(closed, SETTLED), SWITCH_LIMIT + SETTLED,
               lambda: "gate records processed after the door closed: %s" % S.describe(
                   [reg.gate_record(d) for d in GATED]))
    assert not any(outputs(GATED).values()), "an output came back by itself: %s" % outputs(GATED)
    assert not any(requests(GATED).values()), requests(GATED)
    switch_all_on(GATED)                                  # the operator switches on again


def test_all_hv_off_switches_all_off_and_clears_the_requests(everything_off):
    switch_all_on(ALLOFF_SUPPLIES)
    S.put(ALLOFF, 1)
    S.wait_for(lambda: not any(outputs(ALLOFF_SUPPLIES).values()), SWITCH_LIMIT,
               lambda: "every AU output off: %s" % outputs(ALLOFF_SUPPLIES))
    for d in ALLOFF_SUPPLIES:
        assert S.get(reg.role(d, "out_cmd")) == 0, "%s: request cleared" % d
    S.wait_for(lambda: S.get(ALLOFF) == 0, SWITCH_LIMIT, lambda: "%s back to 0: %s" % (
        ALLOFF, S.describe([ALLOFF])))
    assert S.sevr(ALLOFF) == S.NO_ALARM
