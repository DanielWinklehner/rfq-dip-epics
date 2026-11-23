"""Shared by the tests of this case: the supplies, Channel Access and simulator helpers."""
import os
import re
import time

import epics
import pytest

from mist2sim.control import ControlClient

SIM_HOST = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
CONTROL = {"mat_opt": 6001, "mat_co": 6002, "rek": 6003, "rek55": 6004}   # sim.yaml ports + 1000

# PV prefix: (simulator, unit, full-scale voltage V, full-scale current in the PV unit, load ohm,
#             factor from the PV current unit to A)
POLLED = {
    "AU-20P7-1": ("mat_opt", 1, 20000, 15, 4e6, 1e-3),
    "AU-20P7-2": ("mat_opt", 2, 20000, 7.5, 4e6, 1e-3),
    "AU-20P7-3": ("mat_co", 3, 20000, 7.5, 4e6, 1e-3),
    "AU-20P7-4": ("mat_co", 4, 20000, 7.5, 4e6, 1e-3),
    "REK-1": ("rek", 1, 150, 24, 5.0, 1.0),
    "REK-2": ("rek55", 2, 150, 55, 2.0, 1.0),
}
UNPOLLED = "AU-20P7-6"                   # loaded with SCAN_MON/GET/STS=Passive, test only
AU = ["AU-20P7-1", "AU-20P7-2", "AU-20P7-3", "AU-20P7-4"]
SIM_OF = {"AU-20P7-6": ("mat_co", 6), "REK-9": ("rek55", 9)}
SIM_OF.update({k: v[:2] for k, v in POLLED.items()})

READS = ["voltage:get", "voltage:read", "current:get", "current:read", "power:read",
         "status:read", "read_output_status"]
WRITES = ["voltage:setpoint", "current:limit", "SetToggleOutput", "OutputIntlk",
          "ToggleOutput", "output:init"]
INTERNAL = ["_poll:tick", "_poll:gate", "_poll:start", "_poll:done", "_init:probe",
            "_limit:apply", "_limit:send", "_permit:latch",
            # supply_first_contact.db
            "_init:otake", "_init:otake:on", "_init:otake:copy", "_init:otake:off",
            "_init:vtake", "_init:vtake:copy", "_init:vtake:off"]
SUFFIXES = WRITES + READS
UNPOLLED_UNREAD = ["voltage:read", "current:read", "power:read", "status:read"]

GRACE = 5            # the default of the database


def control(prefix_or_chain):
    chain = SIM_OF[prefix_or_chain][0] if prefix_or_chain in SIM_OF else prefix_or_chain
    return ControlClient(SIM_HOST, CONTROL[chain])


def sim_signal(prefix, name, what="value"):
    chain, unit = SIM_OF[prefix]
    with control(chain) as c:
        return c.get("%d.%s" % (unit, name))[what]


def get(pv):
    # use_monitor=False: a fresh read from the IOC. pyepics' default returns the value of its
    # monitor, which right after a completed put can still be the old one (seen: the SEVR of a
    # set that the IOC had already turned INVALID read as 0, once in about 150 puts).
    value = epics.caget(pv, timeout=3, use_monitor=False)
    assert value is not None, "%s does not answer" % pv
    return value


def sevr(pv):
    return get(pv + ".SEVR")


def put(pv, value):
    assert epics.caput(pv, value, wait=True, timeout=10) == 1, "caput %s failed" % pv


def wait_for(cond, timeout, what):
    """Wait until cond() is true. Returns the seconds it took."""
    t0 = time.monotonic()
    while True:
        try:
            if cond():
                return time.monotonic() - t0
        except AssertionError:
            pass
        if time.monotonic() - t0 > timeout:
            pytest.fail("not within %g s: %s" % (timeout, what() if callable(what) else what))
        time.sleep(0.05)


def switch(prefix, on, timeout=5):
    """Request the output on or off and wait until the supply reports it."""
    put(prefix + ":SetToggleOutput", int(on))
    wait_for(lambda: get(prefix + ":status:read") == int(on), timeout,
             "%s:status:read == %d" % (prefix, on))


def all_valid(prefix, suffixes=SUFFIXES):
    return all(sevr("%s:%s" % (prefix, s)) == 0 for s in suffixes)


def not_valid(prefix, suffixes=SUFFIXES):
    """The PVs of `prefix` with an alarm, for failure messages."""
    return [s for s in suffixes
            if epics.caget("%s:%s.SEVR" % (prefix, s), timeout=2, use_monitor=False) != 0]


def invalid(prefix, suffixes):
    return all(sevr("%s:%s" % (prefix, s)) == 3 for s in suffixes)


def sim_log_lines(pattern):
    with open(os.path.join(BUILD, "sim.log")) as f:
        return [l.rstrip() for l in f if re.search(pattern, l)]


def ioc_seconds():
    return get("DEVTEST:heartbeat")


_restarts = [0]


def restart_ioc():
    """Restart the IOC process (harness: a new content of build/ioc-restart) and wait until it
    answers again: the Channel Access connection drops and comes back."""
    pv = epics.PV("DEVTEST:heartbeat")
    assert pv.wait_for_connection(5)
    _restarts[0] += 1
    with open(os.path.join(BUILD, "ioc-restart"), "w") as f:
        f.write("%d\n" % _restarts[0])
    wait_for(lambda: not pv.connected, 15, "the IOC stops")
    wait_for(lambda: pv.connected and pv.get(timeout=1) is not None, 40, "the IOC is back")


def sim_log_since(mark, pattern):
    """Lines of the simulator log after line number `mark` that match `pattern`."""
    with open(os.path.join(BUILD, "sim.log")) as f:
        lines = f.readlines()[mark:]
    return [l.rstrip() for l in lines if re.search(pattern, l)]


def sim_log_mark():
    with open(os.path.join(BUILD, "sim.log")) as f:
        return len(f.readlines())
