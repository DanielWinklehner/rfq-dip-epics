"""Session set-up of the system tests: wait for both IOCs, connect every PV of the registry, take
a snapshot of the state the suite found, and put it back at the end (also after a failure)."""
import time

import pytest

import system as S
from system import reg

# Records whose value or alarm the suite changes only through their own tests; the snapshot keeps
# what they were, and the clean-up writes them back.
snapshot = {}
held_at_start = {}     # simulator -> signals held from outside when the suite started
SETTLED = 15          # seconds after an IOC start
FIRST_CONTACT = 30    # s: probe every 1 s, then GRACE 5 s; 30 s covers a supply answering late


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
    if s["status"] != S.UDF or spec.get("role") == "ilimit":
        # a current limit is restored by autosave at the start: its value is the saved one,
        # also while it is not yet applied to the supply (UDF)
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


def defaults():
    """Every PV of the IOCs' limits.defaults files with its default: {name: value}."""
    out = {}
    for ioc in reg.iocs.values():
        path = S.REPO / ioc["st_cmd"]
        path = path.parent / "limits.defaults"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            words = line.split()
            if len(words) == 2 and not line.startswith("#"):
                out[words[0]] = float(words[1])
    return out


def setting(name):
    if "." in name:
        record, fld = name.split(".", 1)
        return float(S.field(record, fld))
    return float(S.get(name))


def report_changed_settings(request):
    """Print (not fail on) every saved setting that differs from its default when the suite
    starts: an emulation whose settings someone changed is seen, while the suite restores what
    it found."""
    changed = ["%s = %g (default %g)" % (n, setting(n), v) for n, v in sorted(defaults().items())
               if S.connected(n.split(".")[0]) and abs(setting(n) - v) > 1e-9]
    capture = request.config.pluginmanager.getplugin("capturemanager")
    with capture.global_and_fixture_disabled():          # past pytest's capture, as a table
        print("\nsaved settings that differ from limits.defaults at the start: %s"
              % ("; ".join(changed) if changed else "none"))


@pytest.fixture(scope="session", autouse=True)
def system(request):
    """Both IOCs answer and are past their GRACE time; every PV of the registry has a monitor."""
    # Past GRACE, and long enough for the slowest source (NT 20 data output, one record every
    # 8 s) to have sent: the snapshot then shows the system as it runs, not as it starts.
    for ioc, hb in reg.heartbeats().items():
        S.wait_for(lambda: S.connected(hb) and S.get(hb) >= SETTLED, 90,
                   "%s (%s) answers and has run for %d s" % (ioc, hb, SETTLED))
    # First contact: a supply's permit gate acts GRACE s after the supply first answered; until
    # then a request is overwritten by the supply's own state (matsusada_au20p7.db)
    gates = [g for g in (reg.gate_record(d) for d in reg.devices) if g]
    S.wait_for(lambda: all(S.field(g, "DISA") == "0" for g in gates), FIRST_CONTACT,
               lambda: "permit gates enabled after the first contact: %s" % {
                   g: S.field(g, "DISA") for g in gates})
    S.watch(list(reg.pvs))
    report_changed_settings(request)
    for name in reg.pvs:
        if S.connected(name):
            d = S.read(name)
            snapshot[name] = dict(value=d["value"], severity=d["severity"], status=d["status"])
    for sim in reg.simulators:          # every simulator answers before anything starts
        signals = S.control(sim).get()["signals"]
        held_at_start[sim] = {n for n, s in signals.items() if s.get("external")}
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
    last = {n: S.read(n)["timestamp"] for n in names}
    count = {n: 0 for n in names}
    end = time.monotonic() + 2.5
    while time.monotonic() < end:          # advanced twice: processed at least every ~1.2 s
        for n in names:
            t = S.read(n)["timestamp"]
            if t > last[n]:
                last[n], count[n] = t, count[n] + 1
        time.sleep(0.2)
    advanced = {n for n in names if count[n] >= 2}
    return advanced
