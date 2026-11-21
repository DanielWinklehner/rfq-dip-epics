"""Faults, one simulator at a time, for every simulator of the registry: `silent`, `close` and
`garbage` turn every PV whose `fails_with` names that simulator INVALID within the limit of its
device class, while every other PV on both IOCs stays free of INVALID and the scanned ones keep
updating; after `clear` everything recovers without an IOC restart. `trip` where the simulator
type has one, and on a bus with several polled units one unit silent while its neighbours keep
answering."""
import time

import pytest

import system as S
from system import reg
from conftest import snapshot

# Seconds from the fault to "every PV of the simulator INVALID":
INVALID_LIMIT = 5.0          # every polled device: the slowest poll is 2 s (MFC set-point
                             # read-backs) plus a reply timeout of at most 1 s (libcom1)
NT20_LIMIT = 25.0            # NT 20 data output, listen only: one record every 8 s, the PVs turn
                             # INVALID when the last record is older than AGE_LIMIT 20 s
                             # (nt20_monitor.db): at most 8 + 20 s minus the age already reached,
                             # plus the 1 s scan of age:get; 25 s covers it
NT20_GARBAGE_LIMIT = 10.0    # a garbled record arrives within one period (8 s)
RECOVER_LIMIT = 20.0         # back to valid after clear: asyn reconnects a closed port within a
                             # few seconds; then the next poll
IDENTITY_LIMIT = 10.0        # identity records: three queries of 1 s reply timeout each (id,
                             # firmware, channels by forward link), queued behind the board's
                             # data polls, which time out as well
# Identity records (id, firmware, channels) are scanned every 10 s. To keep the suite inside its
# time budget the test processes them once right after injecting and after clearing a fault (a
# client reading them), instead of waiting for their scan; the limits above then apply to them.
WINDOW_LIMIT = 5.0           # every scanned PV of the other devices updates within this time

SLOW_SOURCES = {"nt20_monitor"}


MATSUSADA_LIMIT = 8.0        # the set-point echoes and the SW setting are read every 5 s
                             # (SCAN_GET), behind polls that each wait 200 ms for the silent unit


def limit(sim, mode):
    kind = reg.simulators[sim]["type"]
    if kind in SLOW_SOURCES:
        return NT20_GARBAGE_LIMIT if mode == "garbage" else NT20_LIMIT
    if kind == "matsusada_co":
        return MATSUSADA_LIMIT
    return INVALID_LIMIT


def own_not_polled(name, sim):
    """A PV of a device that is not polled, failing with its own simulator: nothing reads it, so
    it keeps what it had (asserted: it does not turn INVALID either)."""
    spec = reg.pvs[name]
    return reg.not_polled(spec["device"]) and any(
        ref.split(":")[0] == sim for ref in reg.devices[spec["device"]]["simulators"])


_fields = {}


def not_processed(name):
    """An internal record the registry says fails with a simulator, but which nothing processes
    while the device is silent: a seq that runs once at the start (PINI, AU and REK
    :output:init), or an I/O Intr record that is processed only when data arrive (NT 20 :int:*).
    It keeps its last value and severity. FINDING: the registry's fails_with is wrong for them;
    they are left out of the check and their state is collected for
    test_registry_fails_with_of_unprocessed_internal_records."""
    spec = reg.pvs[name]
    if not spec.get("internal"):
        return False
    if name not in _fields:
        _fields[name] = (S.field(name, "SCAN"), S.field(name, "PINI"))
    scan, pini = _fields[name]
    return scan == "I/O Intr" or (spec["type"] == "seq" and scan == "Passive" and pini == "YES")


def expected(sim, unit=None):
    names = [n for n in reg.fails_with(sim, unit) if n in snapshot]
    return [n for n in names if not own_not_polled(n, sim)
            and snapshot[n]["severity"] != S.INVALID]


KNOWN = {}                   # not_processed PV -> severities seen while its simulator was faulted
UNLISTED = {}                # PV of a faulted device, not in fails_with, seen INVALID -> faults


def identity_records(sim):
    out = []
    for d in reg.devices_behind(sim):
        if reg.has_role(d, "id"):
            out.append(reg.role(d, "id"))
    return out


def others_of(sim, unit=None):
    mine = set(reg.fails_with(sim, unit))
    return [n for n in snapshot if n not in mine and snapshot[n]["severity"] != S.INVALID]


def run_fault(sim, mode, live, unit=None, mine=None):
    mine = mine if mine is not None else expected(sim, unit)
    unprocessed = [n for n in mine if not_processed(n)]
    mine = [n for n in mine if n not in unprocessed]
    assert mine, "the registry names no PV that fails with %s" % sim
    others = others_of(sim, unit)
    behind = set(reg.devices_behind(sim, unit))
    watch_update = [n for n in others if n in live and reg.pvs[n]["device"] not in behind]
    S.wait_for(lambda: S.not_invalid(mine), RECOVER_LIMIT,
               lambda: "%s before the fault: %s" % (sim, S.bad(mine, lambda s: s != S.INVALID)))
    stamps = {n: S.read(n)["timestamp"] for n in watch_update}
    lim = limit(sim, mode)
    with S.fault(sim, mode, unit) as f:
        poke(identity_records(sim))
        ident = [n for n in mine if reg.pvs[n].get("role") in ("id", "firmware", "channel_list")]
        if ident:
            lim = max(lim, IDENTITY_LIMIT)
        took = S.wait_for(lambda: S.all_invalid(mine), lim,
                          lambda: "%s %s%s: not INVALID: %s" % (
                              sim, mode, "" if unit is None else " unit %d" % unit,
                              S.bad(mine, lambda s: s == S.INVALID)))
        S.wait_for(lambda: all(S.read(n)["timestamp"] > stamps[n] for n in watch_update),
                   WINDOW_LIMIT, lambda: "other devices stopped updating: %s" % [
                       n for n in watch_update if S.read(n)["timestamp"] <= stamps[n]])
        for n in unprocessed:
            KNOWN.setdefault(n, set()).add(S.sevr(n))
        hit = [n for n in others if S.watched(n).invalid_since(f.t0)]
        for n in hit:
            if reg.pvs[n]["device"] in behind:     # same device, not in fails_with: registry
                UNLISTED.setdefault(n, set()).add("%s %s" % (sim, mode))
        hit = [n for n in hit if reg.pvs[n]["device"] not in behind]
        assert hit == [], "%s %s turned PVs of other devices INVALID: %s" % (
            sim, mode, S.describe(hit))
    poke(identity_records(sim))
    back = S.wait_for(lambda: S.not_invalid(mine), RECOVER_LIMIT,
                      lambda: "%s after clearing %s: still INVALID: %s" % (
                          sim, mode, S.bad(mine, lambda s: s != S.INVALID)))
    print("%s %s: %d PVs INVALID after %.1f s, %d other PVs valid, %d of them updating; "
          "recovered %.1f s after clear" % (sim, mode, len(mine), took, len(others),
                                            len(watch_update), back))
    return took, back


def poke(names):
    """Process records now (a .PROC write that does not wait for the device)."""
    for n in names:
        S.put_field(n, "PROC", 1, wait=False)


SIMS = list(reg.simulators)


@pytest.mark.parametrize("mode", ["silent", "close"])
@pytest.mark.parametrize("sim", SIMS)
def test_fault_turns_its_pvs_invalid_and_recovers(sim, mode, live):
    run_fault(sim, mode, live)


def garbage_expected(sim):
    """With garbled replies every PV that parses a reply turns INVALID. A record that takes any
    line of text (the NT 20 `raw` record) cannot tell, by design."""
    return [n for n in expected(sim) if reg.pvs[n].get("role") != "raw"
            and not (reg.pvs[n].get("internal") and n.endswith(":int:raw"))]


GARBAGE = [pytest.param(s, marks=pytest.mark.xfail(
    reason="FINDING: a garbled NT 20 record does not match the parser of speed and current "
           "(I/O Intr, StreamDevice ignores a mismatching input), raw accepts it and resets "
           "the age: speed:get and current:get keep the last value without alarm",
    strict=True)) if reg.simulators[s]["type"] == "nt20_monitor" else s for s in SIMS]


@pytest.mark.parametrize("sim", GARBAGE)
def test_garbage_turns_its_pvs_invalid_and_recovers(sim, live):
    run_fault(sim, "garbage", live, mine=garbage_expected(sim))


# --- one unit of a bus silent --------------------------------------------------------------------

def polled_units(sim):
    out = []
    for u in reg.units(sim):
        devices = reg.devices_behind(sim, u)
        if devices and not any(reg.not_polled(d) for d in devices):
            out.append(u)
    return out


UNITS = [(s, u) for s in SIMS if len(polled_units(s)) >= 2 for u in polled_units(s)]


@pytest.mark.parametrize("sim,unit", UNITS, ids=["%s:%d" % x for x in UNITS])
def test_one_unit_silent_its_neighbours_keep_answering(sim, unit, live, capsys):
    """Only the PVs of that unit turn INVALID; the neighbours' PVs stay valid and update (with
    each poll of the silent unit waiting for its reply timeout, more slowly: the rate is
    reported)."""
    mine = [n for n in expected(sim, unit) if "%s:%d" % (sim, unit) in reg.pvs[n]["fails_with"]
            and not not_processed(n)]
    neighbours = [u for u in polled_units(sim) if u != unit]
    rates = {}
    for u in neighbours:
        d = reg.devices_behind(sim, u)[0]
        rates[u] = reg.role(d, "vread")
    with S.fault(sim, "silent", unit):
        S.wait_for(lambda: S.all_invalid(mine), limit(sim, "silent"),
                   lambda: "unit %d not INVALID: %s" % (unit, S.bad(mine, lambda s: s == S.INVALID)))
        measured = {u: update_rate(pv, 3.0) for u, pv in rates.items()}
    S.report("%s unit %d silent: neighbours keep %s updates/s of voltage:read" % (
        sim, unit, ", ".join("unit %d %.1f" % kv for kv in measured.items())), capsys)
    for u, r in measured.items():
        assert r > 0.5, "neighbour unit %d updates %.2f/s while unit %d is silent" % (u, r, unit)
    S.wait_for(lambda: S.not_invalid(mine), RECOVER_LIMIT,
               lambda: "unit %d recovers: %s" % (unit, S.bad(mine, lambda s: s != S.INVALID)))


def update_rate(pv, seconds):
    """Processings per second of a record: its monitor events with MDEL -1 for the measurement
    (every processing posted, also an unchanged value)."""
    S.put_field(pv, "MDEL", -1)
    try:
        w = S.watched(pv)
        t0 = time.monotonic()
        S.wait_for(lambda: time.monotonic() - t0 >= seconds, seconds + 1, "measuring")
        events = [t for t, _ in list(w.events) if t >= t0]
        return len(events) / seconds
    finally:
        S.put_field(pv, "MDEL", 0)


# --- trip ------------------------------------------------------------------------------------------

TRIP_TYPES = {"matsusada_co", "tdk_genesys", "mks_rs485", "nt20_monitor"}


@pytest.mark.parametrize("sim", [s for s in SIMS if reg.simulators[s]["type"] not in TRIP_TYPES])
def test_trip_is_refused_where_the_type_has_none(sim):
    """So that a type that gains a trip fault is noticed and gets a test here."""
    with pytest.raises(S.ControlError, match="no trip"):
        S.control(sim).fault("trip")


def test_registry_fails_with_of_unprocessed_internal_records():
    """The registry says these internal records fail with their simulator; the fault tests above
    saw them keep their severity. Expected to fail until the registry (plan/registry.py) leaves
    them out of fails_with, or the databases process them."""
    assert KNOWN, "no fault test ran before this one (select with -k fault)"
    kept = {n: sorted(s) for n, s in KNOWN.items() if s != {S.INVALID}}
    unlisted = {n: sorted(s) for n, s in UNLISTED.items()}
    if kept or unlisted:
        pytest.xfail("FINDING (registry): fails_with names records that nothing processes while "
                     "their device is silent, so they never turn INVALID: %s; and does not name "
                     "records of the faulted device that do turn INVALID: %s" % (kept, unlisted))


# --- trip --------------------------------------------------------------------------------------

TRIP_LIMIT = 3.0             # trip -> the status poll shows it (STS and OUT? 1 s, Opta 0.5 s)


def trip_device(sim):
    """The first polled device behind the simulator, and its unit."""
    for u in (reg.units(sim) or [None]):
        for d in reg.devices_behind(sim, u):
            if not reg.not_polled(d) and reg.devices[d]["class"] != "command":
                return d, u
    raise AssertionError("no polled device behind %s" % sim)


def trip_matsusada(sim, d, unit):
    """A cut-off: status:read shows the output off while the SW setting stays on; a new
    enable (RST) brings it back."""
    cmd, status, sw = (reg.role(d, r) for r in ("out_cmd", "status", "out_state"))
    try:
        S.put(cmd, 1)
        S.wait_for(lambda: S.get(status) == 1, TRIP_LIMIT, lambda: S.describe([status]))
        with S.fault(sim, "trip", unit):
            S.wait_for(lambda: S.get(status) == 0, TRIP_LIMIT,
                       lambda: "cut-off seen: %s" % S.describe([status]))
            assert S.get(sw) == 1, "the SW setting stays on in a cut-off: %s" % S.describe([sw])
        S.put(cmd, 0)
        S.put(cmd, 1)
        S.wait_for(lambda: S.get(status) == 1, TRIP_LIMIT,
                   lambda: "on again after a new enable: %s" % S.describe([status]))
    finally:
        S.put(cmd, 0)


def trip_tdk(sim, d, unit):
    """OVP shutdown: the fault register shows OVP (MAJOR), the output is off; OUT 1 resets."""
    cmd, state, flt = (reg.role(d, r) for r in ("out_cmd", "out_state", "fault"))
    try:
        S.put(cmd, 1)
        S.wait_for(lambda: S.get(state) == 1, TRIP_LIMIT, lambda: S.describe([state]))
        with S.fault(sim, "trip"):
            pass                                  # latched in the supply
        S.wait_for(lambda: S.get(flt) != 0 and S.sevr(flt) == S.MAJOR and S.get(state) == 0,
                   TRIP_LIMIT, lambda: "OVP seen: %s" % S.describe([flt, state]))
        S.put(cmd, 0)
        S.put(cmd, 1)
        S.wait_for(lambda: S.get(flt) == 0 and S.sevr(flt) == S.NO_ALARM, TRIP_LIMIT,
                   lambda: "OVP reset by OUT 1: %s" % S.describe([flt]))
    finally:
        S.put(cmd, 0)
        S.wait_for(lambda: S.get(state) == 0, TRIP_LIMIT, lambda: S.describe([state]))


def trip_mks(sim, d, unit):
    """The unit answers NAK to everything: read-backs INVALID, a set ends in an alarm."""
    sp, cmd = reg.role(d, "sp"), reg.role(d, "sp_cmd")
    try:
        with S.fault(sim, "trip", unit if len(reg.units(sim)) > 1 else None):
            S.wait_for(lambda: S.sevr(sp) == S.INVALID, INVALID_LIMIT, lambda: S.describe([sp]))
            S.put(cmd, sum(reg.pvs[cmd]["test"]) / 2)
            assert S.sevr(cmd) == S.INVALID, "a refused set ends in an alarm: %s" % S.describe([cmd])
        S.wait_for(lambda: S.sevr(sp) == S.NO_ALARM, RECOVER_LIMIT, lambda: S.describe([sp]))
    finally:
        S.put(cmd, conftest_target(cmd))
    assert S.sevr(cmd) == S.NO_ALARM


def trip_nt20(sim, d, unit):
    """The pump fails: FAILURE relay (MAJOR) and state Failure; STOP resets it."""
    pump = next(p for p in reg.devices_behind(sim) if reg.has_role(p, "failure"))
    run, failure, state = (reg.role(pump, r) for r in ("run_cmd", "failure", "state"))
    try:
        S.put(run, 1)
        S.wait_for(lambda: S.get(state) == 1, TRIP_LIMIT, lambda: "accelerating: %s" % S.describe([state]))
        with S.fault(sim, "trip"):
            S.wait_for(lambda: S.get(failure) == 1 and S.sevr(failure) == S.MAJOR and
                       S.get(state) == 3, TRIP_LIMIT,
                       lambda: "failure seen: %s" % S.describe([failure, state]))
            S.put(run, 0)                         # STOP resets the failure
            S.wait_for(lambda: S.get(failure) == 0 and S.get(state) == 0, TRIP_LIMIT,
                       lambda: "reset by stop: %s" % S.describe([failure, state]))
    finally:
        S.put(run, 0)


def conftest_target(name):
    from conftest import write_target
    return write_target(name)


TRIPS = {"matsusada_co": trip_matsusada, "tdk_genesys": trip_tdk, "mks_rs485": trip_mks,
         "nt20_monitor": trip_nt20}
assert set(TRIPS) == TRIP_TYPES


@pytest.mark.parametrize("sim", [s for s in SIMS if reg.simulators[s]["type"] in TRIP_TYPES])
def test_trip(sim):
    d, unit = trip_device(sim)
    TRIPS[reg.simulators[sim]["type"]](sim, d, unit)
