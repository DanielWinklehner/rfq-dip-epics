"""A permit that is lost, not just open: the rack IOC, which serves the permit interlock_open, is
stopped (its connection closes) or paused (it goes silent, nothing closes). A supply on another
IOC that is gated by it (the REK on the platform IOC) switches off, its request is cleared and
nothing comes back by itself when the permit returns; and a platform IOC started while the rack
IOC is down cannot switch the REK on.

Only the REK takes its permit from another IOC in the emulation. The AU supplies are on the rack
IOC with their permit: their link cannot be lost, they have the same records (the mirror
_permit:read in matsusada_au20p7.db) and are tested by test_06 for an open door and test_05 for
a silent interlock box.

The same for the control loops whose permit condition is that PV: in PID they hand back with
"permit N no data" (the condition shows "no data", INVALID), and a request is refused so, also
after a start of the loop's IOC while the permit's IOC is down."""
import time

import pytest

import system as S
from system import reg
from test_09_loop import LOOPS, Loop, fulfil, go_pid, reason, service_alive, start_value

ILK = next(d for d, dev in reg.devices.items() if dev["class"] == "interlock")
PERMIT = reg.role(ILK, "open")
PERMIT_IOC = reg.devices[ILK]["ioc"]
RACK = S.ioc_container(PERMIT_IOC)
GATED = [d for d in reg.devices if reg.has_role(d, "out_cmd") and reg.gate_record(d)
         and reg.devices[d]["ioc"] != PERMIT_IOC]

CONN_TMO = 5.0         # EPICS_CA_CONN_TMO of the platform IOC (iocHV/st.cmd)
# Seconds from the loss to the output off:
STOP_LIMIT = 2.0       # the connection closes: the mirror is INVALID at its next scan (0.1 s),
                       # the gate follows by its CP link, the switching protocol (PRIO HIGH)
PAUSE_LIMIT = 2 * CONN_TMO + 1.0 + STOP_LIMIT   # silent peer: CA sends an echo after CONN_TMO
                       # of silence and declares the circuit unresponsive when the echo is not
                       # answered within CONN_TMO again (measured: 10.0 s)
BACK_LIMIT = 60.0      # an IOC up again: its start, the supplies' first contact and GRACE
SETTLED = 3.0          # s the output is watched to stay off after the permit returned


LOOPS_HERE = [Loop(d) for d in LOOPS]
# (loop, n) for every loop condition that is the permit PV
LOOP_PERMITS = [(lp, n) for lp in LOOPS_HERE for n, (pv, _, _) in enumerate(lp.conditions, 1)
                if pv == PERMIT]


def loops_in_pid():
    for lp, _ in LOOP_PERMITS:
        service_alive(lp)
        for pv, required, _ in lp.conditions:
            fulfil(pv, required)
        S.put(lp["slew"], 0.5)
        S.put(lp.act, start_value(lp))
    time.sleep(1.5)                                 # the service has seen the heartbeat count
    for lp, _ in LOOP_PERMITS:
        go_pid(lp)


def loops_handed_back(limit, t0, capsys):
    for lp, n in LOOP_PERMITS:
        S.wait_for(lambda: S.get(lp["mode"]) == 0, limit - (time.monotonic() - t0),
                   lambda: "hand-back: %s" % S.describe([lp["mode"], lp["reason"], lp["permit%d" % n]]))
        took = time.monotonic() - t0
        assert reason(lp) == "permit %d no data" % n, reason(lp)
        assert S.get(lp["mode_cmd"]) == 0
        record = lp["permit%d" % n]
        assert S.get(record, as_string=True) == "no data" and S.sevr(record) == S.INVALID
        S.report("%s: hand-back '%s' after %.1f s (limit %.0f s)" % (lp.device, reason(lp), took, limit),
                 capsys)


def output_on(device):
    sim, unit = reg.devices[device]["simulators"][0].split(":")
    return S.sim_value(sim, "%s.output" % unit) == 1.0


def gates_enabled(ioc):
    gates = [g for g in (reg.gate_record(d) for d in reg.devices) if g and reg.pvs[g]["ioc"] == ioc]
    S.wait_for(lambda: all(S.field(g, "DISA") == "0" for g in gates), BACK_LIMIT,
               "gate records of %s enabled (first contact)" % ioc)


def ioc_up(ioc):
    hb = reg.iocs[ioc]["roles"]["heartbeat"]
    S.wait_for(lambda: S.connected(hb) and S.get(hb) >= 1, BACK_LIMIT, "%s up" % ioc)
    gates_enabled(ioc)


def mirror(device):
    """The supply's own record of the permit (_permit:read): valid once the link is back."""
    sims = set(reg.devices[ILK]["simulators"])
    return next(n for n, s in reg.devices[device]["pvs"].items() if s.get("internal")
                and s["type"] == "ai" and sims & set(s.get("fails_with", [])))


def permit_seen(devices):
    """Every supply sees the permit again (its link reconnected)."""
    took = S.wait_for(lambda: all(S.sevr(mirror(d)) != S.INVALID for d in devices), BACK_LIMIT,
                      lambda: "permit links back: %s" % S.describe([mirror(d) for d in devices]))
    return took


def switch_on(devices):
    for d in devices:
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: all(output_on(d) for d in devices), 5.0, "outputs on")


def off_and_cleared(devices):
    return all(not output_on(d) and S.get(reg.role(d, "out_cmd")) == 0 for d in devices)


@pytest.fixture
def rack_back():
    """Whatever the test did to the rack IOC: running and past its first contact afterwards, the
    outputs off."""
    state = {"down": None}
    yield state
    if state["down"] == "pause":
        S.container("unpause", RACK)
    elif state["down"] == "stop":
        S.container("start", RACK)
    ioc_up(PERMIT_IOC)
    permit_seen(GATED)
    for d in GATED:
        S.put(reg.role(d, "out_cmd"), 0)
    for lp, _ in LOOP_PERMITS:
        S.put(lp["mode_cmd"], 0)


def test_registry_has_a_supply_gated_from_another_ioc():
    assert GATED, "no supply takes its permit from another IOC"


@pytest.mark.parametrize("how", ["stop", "pause"])
def test_lost_permit_switches_off_and_latches(rack_back, how, capsys):
    switch_on(GATED)
    loops_in_pid()
    t0 = time.monotonic()
    S.container(how, RACK)
    rack_back["down"] = how
    limit = STOP_LIMIT if how == "stop" else PAUSE_LIMIT
    S.wait_for(lambda: off_and_cleared(GATED), limit - (time.monotonic() - t0),
               lambda: "off and cleared after the rack IOC's %s: %s" % (how, {
                   d: (output_on(d), S.get(reg.role(d, "out_cmd"))) for d in GATED}))
    took = time.monotonic() - t0
    S.report("%s of the rack IOC: %s off and request cleared after %.1f s (limit %.0f s)" % (
        how, ", ".join(GATED), took, limit), capsys)
    loops_handed_back(limit, t0, capsys)
    for d in GATED:                                 # a request while the permit is lost
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: off_and_cleared(GATED), 2.0, "a request while lost is cleared at once")
    S.container("unpause" if how == "pause" else "start", RACK)
    rack_back["down"] = None
    ioc_up(PERMIT_IOC)
    back = permit_seen(GATED)
    S.report("the permit link back %.1f s after the rack IOC's first contact" % back, capsys)
    time.sleep(SETTLED)
    assert off_and_cleared(GATED), "an output came back by itself"
    switch_on(GATED)                                # the operator switches on again


def test_platform_ioc_started_while_the_permit_is_down(rack_back):
    ioc = reg.devices[GATED[0]]["ioc"]
    S.container("stop", RACK)
    rack_back["down"] = "stop"
    S.container("restart", S.ioc_container(ioc))
    ioc_up(ioc)
    for d in GATED:
        S.put(reg.role(d, "out_cmd"), 1)
    S.wait_for(lambda: off_and_cleared(GATED), 2.0, "request cleared at once")
    time.sleep(SETTLED)
    assert off_and_cleared(GATED), "switched on without its permit"
    for lp, n in LOOP_PERMITS:                      # never connected since the start: no data
        service_alive(lp)
        record = lp["permit%d" % n]
        assert S.get(record, as_string=True) == "no data" and S.sevr(record) == S.INVALID
        S.put(lp["mode_cmd"], 1)
        S.wait_for(lambda: S.get(lp["mode_cmd"]) == 0, 1.0, "refused")
        assert S.get(lp["mode"]) == 0 and reason(lp) == "permit %d no data" % n, reason(lp)
