"""Clean end: the suite leaves the system as it found it. No fault in any simulator and no
simulator signal held, every output off, every valve closed, both pumps stopped, every set point
at the value the suite found, and every PV back to the severity it had then."""
import pytest

import system as S
from system import reg
from conftest import snapshot, write_target

SETTLE_LIMIT = 20.0      # the last test's device may still be recovering (identity scan 10 s)


def test_no_fault_and_no_held_signal_in_any_simulator():
    bad = {}
    for sim in reg.simulators:
        state = S.control(sim).get()
        held = [n for n, s in state["signals"].items() if s.get("external")]
        if state["faults"] or held:
            bad[sim] = {"faults": state["faults"], "held": held}
    assert bad == {}


def test_outputs_off_valves_closed_pumps_stopped():
    off = []
    for d, dev in reg.devices.items():
        roles = dev.get("roles", {})
        for role in ("out_cmd", "out_state", "run_cmd", "run_state"):
            if role in roles:
                off.append(roles[role])
        if dev["class"] == "valve":
            off += [c["roles"]["state"] for c in dev["channels"].values()] + \
                   [c["roles"]["cmd"] for c in dev["channels"].values()]
        if dev["class"] == "turbo":
            S.wait_for(lambda: S.get(roles["state"]) == 0, SETTLE_LIMIT,
                       lambda: "pump stopped: %s" % S.describe([roles["state"]]))
    on = [n for n in off if S.get(n) != 0]
    assert on == [], "not off: %s" % S.describe(on)
    for d in reg.devices:          # the real outputs, also of a supply that is not polled
        for ref in reg.devices[d]["simulators"]:
            sim, _, unit = ref.partition(":")
            if unit and reg.simulators[sim]["type"] == "matsusada_co":
                assert S.sim_value(sim, "%s.output" % unit) == 0.0, "%s output on" % d


def test_set_points_as_found():
    changed = [n for n in reg.writes() if n in snapshot and reg.pvs[n].get("readback") is not None
               and S.get(n) != pytest.approx(write_target(n), abs=1e-6)]
    assert changed == [], S.describe(changed)


def test_every_pv_back_to_its_severity():
    names = [n for n in snapshot if snapshot[n]["severity"] != S.INVALID]
    S.wait_for(lambda: S.not_invalid(names), SETTLE_LIMIT,
               lambda: "INVALID at the end: %s" % S.bad(names, lambda s: s != S.INVALID))
