"""Across the two IOCs: an open interlock door (old interlock box, rack IOC) forces off the
outputs of every supply gated by the permit: the high-voltage supplies on the rack IOC and the
filament discharge supply on the platform IOC (through a Channel Access link). When the door
closes, the outputs whose request is still set come back ON by themselves: the lab's behaviour
of 2023, kept on purpose and open for the owner (P16). It is asserted as it is, so that a later
change is noticed. "All HV off" switches all five AU supplies off and clears their requests."""
import pytest

import system as S
from system import reg

ILK = "ilk_old"
PERMIT = reg.role(ILK, "open")
INTERLOCK_SIM = reg.devices[ILK]["simulators"][0]
DOOR = sorted(reg.devices[ILK]["channels"])[0]          # i1: a door switch, signal of the same name
SWITCH_LIMIT = 3.0     # permit -> output: OutputIntlk follows the permit by a CP link (and scans
                       # every 1 s); the switching protocol is sent at once (PRIO HIGH)
RETURN_LIMIT = 5.0     # the door closed again: the same chain back


def gated():
    """Devices whose output the permit gates: those with an internal record failing with the
    interlock box (OutputIntlk), and an output request."""
    out = []
    for d, dev in reg.devices.items():
        if reg.has_role(d, "out_cmd") and any(
                s.get("internal") and INTERLOCK_SIM in s.get("fails_with", [])
                for s in dev["pvs"].values()):
            out.append(d)
    return out


GATED = gated()
ALLOFF_DEV = next(d for d, dev in reg.devices.items() if dev["class"] == "command")
ALLOFF = reg.role(ALLOFF_DEV, "cmd")
ALLOFF_SUPPLIES = [d for d in reg.devices if d != ALLOFF_DEV and any(
    s.split(":")[0] in reg.devices[ALLOFF_DEV]["simulators"] and ":" in s
    for s in reg.devices[d]["simulators"])]


def output_on(device):
    """The supply's real output (simulator signal <unit>.output: lens 3 is not polled, so its
    status PV cannot show it)."""
    sim, unit = reg.devices[device]["simulators"][0].split(":")
    return S.sim_value(sim, "%s.output" % unit) == 1.0


def outputs(devices):
    return {d: output_on(d) for d in devices}


@pytest.fixture
def everything_off():
    yield
    if (INTERLOCK_SIM, DOOR) in S.forced:
        S.sim_release(INTERLOCK_SIM, DOOR)
    for d in GATED:
        S.put(reg.role(d, "out_cmd"), 0)
    S.wait_for(lambda: not any(outputs(GATED).values()), SWITCH_LIMIT,
               lambda: "outputs off after the test: %s" % outputs(GATED))


def test_registry_has_the_gated_supplies():
    assert len(GATED) == 6, GATED              # five AU supplies, the REK
    assert {reg.devices[d]["ioc"] for d in GATED} == set(reg.iocs)   # both IOCs
    assert len(ALLOFF_SUPPLIES) == 5, ALLOFF_SUPPLIES


def test_open_door_forces_outputs_off_and_closing_brings_them_back(everything_off):
    for d in GATED:
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: all(outputs(GATED).values()), SWITCH_LIMIT,
               lambda: "all gated outputs on: %s" % outputs(GATED))
    S.sim_set(INTERLOCK_SIM, DOOR, 0)                     # door open
    S.wait_for(lambda: S.get(PERMIT) == 1, SWITCH_LIMIT, lambda: S.describe([PERMIT]))
    S.wait_for(lambda: not any(outputs(GATED).values()), SWITCH_LIMIT,
               lambda: "outputs forced off by the open door: %s" % outputs(GATED))
    for d in GATED:
        assert S.get(reg.role(d, "out_cmd")) == 1, "%s: the request stays set" % d
        if reg.has_role(d, "status") and not reg.not_polled(d):
            S.wait_for(lambda: S.get(reg.role(d, "status")) == 0, SWITCH_LIMIT,
                       lambda: S.describe([reg.role(d, "status")]))
    S.sim_set(INTERLOCK_SIM, DOOR, 1)                     # door closed
    S.sim_release(INTERLOCK_SIM, DOOR)
    S.wait_for(lambda: S.get(PERMIT) == 0, SWITCH_LIMIT, lambda: S.describe([PERMIT]))
    # P16, kept on purpose: nobody switches anything, the outputs come back
    S.wait_for(lambda: all(outputs(GATED).values()), RETURN_LIMIT,
               lambda: "outputs back ON by themselves after the door closed (P16): %s"
               % outputs(GATED))


def test_all_hv_off_switches_all_five_off_and_clears_the_requests(everything_off):
    for d in ALLOFF_SUPPLIES:
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: all(outputs(ALLOFF_SUPPLIES).values()), SWITCH_LIMIT,
               lambda: "all AU outputs on: %s" % outputs(ALLOFF_SUPPLIES))
    S.put(ALLOFF, 1)
    S.wait_for(lambda: not any(outputs(ALLOFF_SUPPLIES).values()), SWITCH_LIMIT,
               lambda: "every AU output off: %s" % outputs(ALLOFF_SUPPLIES))
    for d in ALLOFF_SUPPLIES:
        assert S.get(reg.role(d, "out_cmd")) == 0, "%s: request cleared" % d
    S.wait_for(lambda: S.get(ALLOFF) == 0, SWITCH_LIMIT, lambda: "%s back to 0: %s" % (
        ALLOFF, S.describe([ALLOFF])))
    assert S.sevr(ALLOFF) == S.NO_ALARM
