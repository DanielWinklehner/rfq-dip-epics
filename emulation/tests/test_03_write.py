"""Write: every set point and switch of the registry is written inside its safe test range and its
read-back follows within a stated time; the set record ends without alarm (an acknowledged set
was acknowledged, a Matsusada set found its echo). Afterwards each device is back where it was."""
import time

import pytest

import system as S
from system import reg
from conftest import baseline_ok, snapshot, write_target

# Read-back limits, seconds from the completed caput:
ECHO_LIMIT = 5.0     # an echo or state read-back: the Matsusada :get records are read by a forward
                     # link right after the set, behind the polls of the chain (device test: 3 s);
                     # MFC:getSP and :getWink are polled every 2 s; valves and turbopump relays come
                     # with the next poll of their board (0.1 s and 0.5 s)
FOLLOW_LIMIT = 10.0  # a measured output (TDK voltage:read, current:read): the supply follows with
                     # its time constant (0.1 s) and is polled at 10 Hz; 10 s as in the TDK test
RECOVER_LIMIT = 15.0 # every PV of the device back to its severity before the test (the nAIM
                     # strikes for some seconds after it is switched on)
MEASURED = ("vread", "iread")


def is_command(name):
    """A write without read-back and without acknowledgement (AU:alloff:set): nothing can show
    that it arrived, so it is tested by what it does (test_06_interlock)."""
    spec = reg.pvs[name]
    return spec.get("readback") is None and not spec["ack"]


WRITES = [n for n in reg.writes() if not is_command(n)]


def test_commands_are_only_command_devices():
    commands = [n for n in reg.writes() if is_command(n)]
    assert all(reg.devices[reg.pvs[n]["device"]]["class"] == "command" for n in commands), commands


def is_switch(name):
    """An on/off write: a bo record, or a channel switch of a board written through an ao (the
    valve relays s5 to s8: the relay is energised only by exactly 1)."""
    spec = reg.pvs[name]
    return spec["type"] in ("bo", "mbbo") or (spec.get("role") == "cmd" and "channel" in spec)


def write_values(name, cap=None):
    """Two values inside the test range (below `cap`, the largest value the device can reach
    now, where one is known)."""
    spec = reg.pvs[name]
    lo, hi = spec["test"]
    if cap is not None:
        hi = min(hi, cap)
    if is_switch(name):
        target = write_target(name)
        if spec.get("readback") is None:
            return [0, 1]                  # ends at 1: see write_target
        # only values of the test range: a loop's mode request is written MANUAL only
        return [v for v in (1 - int(target), int(target)) if lo <= v <= hi]
    return [lo + 0.37 * (hi - lo), lo + 0.71 * (hi - lo)]


def tolerance(name):
    lo, hi = reg.pvs[name]["test"]
    return 0 if is_switch(name) else 0.01 * (hi - lo)


def device_pvs(device):
    return [n for n in reg.devices[device]["pvs"] if n in snapshot]


class OutputOn:
    """For a set point whose read-back is a measured output: the output on, the other set point at
    the end of its test range (so that this one is the limiting one), and back afterwards."""

    def __init__(self, name):
        spec = reg.pvs[name]
        self.device = spec["device"]
        rb = spec.get("readback")
        self.needed = rb is not None and reg.pvs[rb].get("role") in MEASURED
        self.readback = rb
        self.name = name
        self.cap = None
        other = {"vset": "iset", "iset": "vset"}.get(spec.get("role"))
        self.other = reg.role(self.device, other) if self.needed and other else None

    def __enter__(self):
        if not self.needed:
            return self
        if self.other:
            S.put(self.other, reg.pvs[self.other]["test"][1])
        if self.other and reg.pvs[self.readback]["role"] == "iread":
            S.put(self.name, reg.pvs[self.name]["test"][1])     # constant voltage first
        S.put(reg.role(self.device, "out_cmd"), 1)
        state = reg.role(self.device, "out_state")
        S.wait_for(lambda: S.get(state) == 1, ECHO_LIMIT, lambda: "output on: %s" % S.describe([state]))
        self.cap = None
        if self.other and reg.pvs[self.readback]["role"] == "iread":
            # constant current needs a current below what the voltage at the end of its range
            # drives through the load: measure that (constant voltage now) and stay below it
            rb = self.readback
            S.wait_fresh(rb, time.time() + 1, lambda v: True, FOLLOW_LIMIT, "settled")
            self.cap = 0.9 * S.get(rb)
        return self

    def __exit__(self, *exc):
        if not self.needed:
            return
        cmd = reg.role(self.device, "out_cmd")
        S.put(cmd, write_target(cmd))
        state = reg.role(self.device, "out_state")
        S.wait_for(lambda: S.get(state) == write_target(cmd), ECHO_LIMIT,
                   lambda: "output back to %r: %s" % (write_target(cmd), S.describe([state])))
        if self.other:
            S.put(self.other, write_target(self.other))


@pytest.mark.parametrize("name", WRITES)
def test_write_and_read_back(name):
    spec = reg.pvs[name]
    device = spec["device"]
    rb = spec.get("readback")
    S.wait_for(lambda: baseline_ok(device_pvs(device)), RECOVER_LIMIT,
               lambda: "%s before the test: %s" % (device, S.describe(device_pvs(device))))
    measured = rb is not None and reg.pvs[rb].get("role") in MEASURED
    limit = FOLLOW_LIMIT if measured else ECHO_LIMIT
    tol = tolerance(name)
    try:
        with OutputOn(name) as out:
            for value in write_values(name, out.cap):
                t_put = time.time()
                S.put(name, value)
                assert S.sevr(name) == S.NO_ALARM, "after writing %r: %s" % (value, S.describe([name]))
                if rb is None:
                    continue
                took = S.wait_fresh(rb, t_put, lambda v: abs(v - value) <= tol, limit,
                                    "%s follows %s := %r (tolerance %g)" % (rb, name, value, tol))
                print("%s := %r: %s follows after %.2f s" % (name, value, rb, took))
    finally:
        target = write_target(name)
        changed = S.get(name) != target        # the sequence may already end on it
        t_put = time.time()
        S.put(name, target)
    if rb is not None and not measured and changed:
        S.wait_fresh(rb, t_put, lambda v: abs(v - target) <= tol, limit,
                     "%s back to %r" % (rb, target))
    S.wait_for(lambda: baseline_ok(device_pvs(device)), RECOVER_LIMIT,
               lambda: "%s after the test: %s" % (device, S.describe(device_pvs(device))))


LIMITED = [d for d in reg.devices if reg.has_role(d, "ilimit")]


@pytest.mark.parametrize("device", LIMITED)
def test_switching_on_sends_the_current_limit(device):
    """The supply forgot its limit (power cycle, emulated in the simulator); switching on sends
    the saved limit: afterwards the limit the supply reports equals current:limit."""
    sim, unit = reg.devices[device]["simulators"][0].split(":")
    limit, reported, cmd, state = (reg.role(device, r)
                                   for r in ("ilimit", "ilimit_get", "out_cmd", "out_state"))
    tol = tolerance(limit)
    S.sim_set(sim, "%s.iset" % unit, 0.0)
    S.sim_release(sim, "%s.iset" % unit)
    try:
        t_on = time.time()
        S.put(cmd, 1)
        S.wait_fresh(reported, t_on, lambda v: abs(v - S.get(limit)) <= tol, ECHO_LIMIT,
                     "%s reports the limit %r after switching on" % (reported, S.get(limit)))
        S.wait_for(lambda: S.get(state) == 1, ECHO_LIMIT, lambda: S.describe([state]))
    finally:
        S.put(cmd, 0)
        S.wait_for(lambda: S.get(state) == 0, ECHO_LIMIT, lambda: S.describe([state]))
