"""Session set-up of the system tests: wait for both IOCs, connect every PV of the registry, take
a snapshot of the state the suite found, and put it back at the end (also after a failure)."""
import time

import pytest

import system as S
from system import reg

# Records whose value or alarm the suite changes only through their own tests; the snapshot keeps
# what they were, and the clean-up writes them back.
snapshot = {}
SETTLED = 15          # seconds after an IOC start


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: needs more than a minute; excluded by default, "
                                       "include with ARGS='-m slow' or ARGS='-m \"\"'")


def write_target(name):
    """What a written PV is set to when the suite leaves: the value it had when the suite started.
    A set record that had never been written (UDF) gets the value of its read-back then; one
    without read-back gets the upper end of its test range (AIM:enable: gauge on, the state the
    gauge starts in, which the read test checks through the pressure)."""
    s = snapshot[name]
    spec = reg.pvs[name]
    if s["status"] != S.UDF:
        return s["value"]
    rb = spec.get("readback")
    if rb:
        return snapshot[rb]["value"]
    return spec["test"][1]


def restore_writes(names=None):
    """Write the set points and switches back to what the suite found. Switches and runs first
    (outputs off, valves closed, pumps stopped), then the set points."""
    names = [n for n in (names or reg.writes()) if reg.pvs[n].get("readback") is not None
             or reg.pvs[n]["ack"]]                       # a command (AU:alloff:set) is not undone
    switches = [n for n in names if reg.pvs[n]["test"] == [0, 1]]
    for n in switches + [n for n in names if n not in switches]:
        target = write_target(n)
        d = S.read(n)
        if d["value"] != target or d["severity"] == S.INVALID:
            S.put(n, target)


@pytest.fixture(scope="session", autouse=True)
def system():
    """Both IOCs answer and are past their GRACE time; every PV of the registry has a monitor."""
    # Past GRACE, and long enough for the slowest source (NT 20 data output, one record every
    # 8 s) to have sent: the snapshot then shows the system as it runs, not as it starts.
    for ioc, hb in reg.heartbeats().items():
        S.wait_for(lambda: S.connected(hb) and S.get(hb) >= SETTLED, 90,
                   "%s (%s) answers and has run for %d s" % (ioc, hb, SETTLED))
    S.watch(list(reg.pvs))
    for name in reg.pvs:
        if S.connected(name):
            d = S.read(name)
            snapshot[name] = dict(value=d["value"], severity=d["severity"], status=d["status"])
    for sim in reg.simulators:
        S.control(sim).info()           # every simulator answers before anything starts
    yield
    problems = S.clear_everything()
    try:
        restore_writes([n for n in reg.writes() if n in snapshot])
    except BaseException as exc:          # noqa: BLE001
        problems.append("restoring the set points: %r" % exc)
    if problems:
        print("\nclean-up problems: %s" % problems)


def baseline_ok(names):
    """Severity of each PV no worse than when the suite started (INVALID only if it was)."""
    return all(S.sevr(n) <= max(snapshot[n]["severity"], S.MAJOR)
               if snapshot[n]["severity"] != S.INVALID else True for n in names)


@pytest.fixture(scope="session")
def live():
    """PVs whose record is processed at least every 2 s (time stamp advances): the ones a fault
    test can watch "keep updating". Found by observation, so a database change of a scan rate
    does not need a test change."""
    names = [n for n in reg.pvs if n in snapshot]
    t0 = {n: S.read(n)["timestamp"] for n in names}
    end = time.monotonic() + 2.5
    advanced = set()
    while time.monotonic() < end:
        for n in names:
            if n not in advanced and S.read(n)["timestamp"] > t0[n]:
                advanced.add(n)
        time.sleep(0.2)
    return advanced
