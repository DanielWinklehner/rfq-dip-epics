"""After every test: the case back in its normal state, also when the test failed, so that one
failure shows as one failure. Faults cleared, every unit in remote control, signals released,
the permit closed and valid, every output request off."""
import time

import epics
import pytest

from mat import AU, CONTROL, POLLED, control

UNITS = {"mat_opt": [1, 2], "mat_co": [3, 4, 6], "rek": [1], "rek55": [2, 9]}


def restore():
    problems = []
    for chain in CONTROL:
        try:
            with control(chain) as c:
                c.clear()
                for name, state in c.get()["signals"].items():
                    if state["external"] and not name.endswith(".remote"):
                        c.release(name)
                for u in UNITS[chain]:
                    c.set("%d.remote" % u, 1)
                    c.release("%d.remote" % u)
        except Exception as exc:                    # report, go on with the rest
            problems.append("%s: %s" % (chain, exc))
    epics.caput("interlock_open.ZSV", "NO_ALARM", wait=True, timeout=5)
    epics.caput("interlock_open", 0, wait=True, timeout=5)
    for d in list(POLLED) + ["AU-20P7-6", "REK-9"]:
        epics.caput(d + ":SetToggleOutput", 0, wait=True, timeout=5)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 5:                # outputs off (not during a GRACE period)
        if all(epics.caget(d + ":status:read", timeout=1, use_monitor=False) in (0, 2, None) for d in POLLED):
            break
        time.sleep(0.2)
    return problems


@pytest.fixture(autouse=True)
def back_to_normal():
    yield
    problems = restore()
    assert not problems, problems
