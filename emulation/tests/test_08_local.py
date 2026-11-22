"""Local control at system level, for one AU supply and for the REK: the front panel takes local
control (simulator signal <unit>.remote = 0), status:read shows it with MINOR and the status polls
do not take it back (REN is sent only at the first contact and with every switching); a voltage
set ends INVALID and is not executed; switching from the control system takes control back."""
import time

import pytest

import system as S
from system import reg
from conftest import write_target

LIMIT = 3.0            # status:read is polled every 1 s (SCAN_STS); the echo after a set at once
POLLS = 2              # status polls that must keep showing local control


def local_devices():
    """One AU supply (a chain with several units) and the REK (a line of its own)."""
    out = {}
    for d, dev in reg.devices.items():
        if not reg.has_role(d, "status") or not dev["simulators"]:
            continue
        sim = dev["simulators"][0].split(":")[0]
        if reg.simulators[sim]["type"] != "matsusada_co":
            continue
        out.setdefault(len(reg.units(sim)) > 1, d)
    return [out[k] for k in sorted(out)]


DEVICES = local_devices()


def state(device, word):
    return reg.pvs[reg.role(device, "status")]["states"].index(word)


def test_one_au_supply_and_the_rek():
    assert len(DEVICES) == 2, DEVICES


@pytest.mark.parametrize("device", DEVICES)
def test_front_panel_takes_local_control_and_switching_takes_it_back(device):
    sim, unit = reg.devices[device]["simulators"][0].split(":")
    status, cmd, vset = (reg.role(device, r) for r in ("status", "out_cmd", "vset"))
    remote = "%s.remote" % unit
    try:
        S.put(cmd, 1)
        S.wait_for(lambda: S.get(status) == state(device, "ON"), LIMIT, lambda: S.describe([status]))
        S.sim_set(sim, remote, 0)                       # the front panel takes control ...
        S.sim_release(sim, remote)                      # ... and keeps it (the supply's state)
        S.wait_for(lambda: S.get(status) == state(device, "ON, LOCAL"), LIMIT,
                   lambda: "local control shown: %s" % S.describe([status]))
        assert S.sevr(status) == S.MINOR, S.describe([status])
        since = time.time()
        S.wait_fresh(status, since + POLLS - 1, lambda v: v == state(device, "ON, LOCAL"),
                     LIMIT + POLLS, "still local after %d status polls" % POLLS)
        assert S.sim_value(sim, remote) == 0.0, "a status poll took remote control back"
        before = S.sim_value(sim, "%s.vset" % unit, "target")
        lo, hi = reg.pvs[vset]["test"]
        S.put(vset, lo + 0.61 * (hi - lo))
        assert S.sevr(vset) == S.INVALID, "a set in local control ends without alarm: %s" % (
            S.describe([vset]))
        assert S.sim_value(sim, "%s.vset" % unit, "target") == before, "executed in local control"
        S.put(cmd, 0)                                   # switching sends REN
        S.wait_for(lambda: S.get(status) == state(device, "OFF"), LIMIT,
                   lambda: "remote again after switching: %s" % S.describe([status]))
        assert S.sevr(status) == S.NO_ALARM
        assert S.sim_value(sim, remote) == 1.0
    finally:
        if (sim, remote) in S.forced:
            S.sim_release(sim, remote)
        S.put(cmd, 0)
        S.put(vset, write_target(vset))
    assert S.sevr(vset) == S.NO_ALARM, "the set point after taking control back: %s" % (
        S.describe([vset]))
