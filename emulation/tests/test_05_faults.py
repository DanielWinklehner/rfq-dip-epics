"""Faults, one simulator at a time, for every simulator of the registry: `silent`, `close` and
`garbage` turn every PV of the registry's fault list for that mode (`fails_with` for silent and
garbage, `fails_closed` for close) INVALID within the limit of its device class, while every
other PV on both IOCs stays free of INVALID and the scanned ones keep updating; after `clear` everything recovers without an IOC restart. `trip` where the simulator
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
NT20_GARBAGE_LIMIT = 13.0    # a garbled record arrives within one period (8 s); speed and
                             # current turn INVALID after two 1 s scans with a record that does
                             # not parse (nt20_monitor.db)
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


def key(mode):
    """The registry's fault list for a fault mode: a closed connection fails more records (I/O
    Intr records of a listen-only port, records that write to a device record) than silence."""
    return "fails_closed" if mode == "close" else "fails_with"


def expected(sim, unit=None, mode="silent"):
    """Every PV the registry lists for this fault. Not filtered: a listed PV that is INVALID
    before the fault, or does not turn INVALID, fails the test."""
    return reg.fails_with(sim, unit, key(mode))


HOLD = 1.0                   # s every listed PV stays INVALID after all of them are
MATSUSADA_CLOSE_HOLD = 8.0   # Matsusada, closed port: a monitor cycle that does not finish is
                             # restarted by the watchdog after POLL_LIMIT (30) ticks of SCAN_MON
                             # (0.1 s) = 3 s; a listed record must stay INVALID through two such
                             # restarts
QUIET = 1.0                  # s without any INVALID before a fault starts (the last test's
                             # device has settled)


def hold(sim, mode):
    if mode == "close" and reg.simulators[sim]["type"] == "matsusada_co":
        return MATSUSADA_CLOSE_HOLD
    return HOLD


def quiet(names, seconds):
    """No INVALID posted in the last `seconds` and none now, from the monitors: a fresh read of
    some 200 PVs every 0.1 s loads the IOCs enough to make a Matsusada poll miss its 150 ms reply
    timeout now and then."""
    since = time.monotonic() - seconds
    return all(not S.watched(n).invalid_since(since) and S.watched(n).severity() != S.INVALID
               for n in names)


def steady_invalid(name, since):
    """INVALID now, and no other severity posted since `since`."""
    w = S.watched(name)
    with w.lock:
        moved = any(t >= since and sv != S.INVALID for t, sv in w.events)
    return not moved and S.sevr(name) == S.INVALID


UNLISTED = {}                # PV of a faulted device, not in its fault list, seen INVALID -> faults
RAN = set()                  # (sim, mode) of the fault tests that ran


def identity_records(sim):
    out = []
    for d in reg.devices_behind(sim):
        if reg.has_role(d, "id"):
            out.append(reg.role(d, "id"))
    return out


def others_of(sim, unit=None, mode="silent"):
    mine = set(reg.fails_with(sim, unit, key(mode)))
    return [n for n in snapshot if n not in mine and snapshot[n]["severity"] != S.INVALID]


def run_fault(sim, mode, live, unit=None, mine=None, keep_valid=()):
    """keep_valid: PVs of the fault list that must stay valid under this mode (NT 20 raw under
    garbage)."""
    mine = mine if mine is not None else expected(sim, unit, mode)
    assert mine, "the registry names no PV that fails with %s %s" % (sim, mode)
    others = others_of(sim, unit, mode) + list(keep_valid)
    behind = set(reg.devices_behind(sim, unit))
    watch_update = [n for n in others if n in live and reg.pvs[n]["device"] not in behind]
    S.wait_for(lambda: S.not_invalid(mine), RECOVER_LIMIT,
               lambda: "%s before the fault: %s" % (sim, S.bad(mine, lambda s: s != S.INVALID)))
    S.wait_for(lambda: quiet(others, QUIET), RECOVER_LIMIT, interval=0.5, what=
               lambda: "the other PVs before the fault: %s" % [
                   n for n in others if S.watched(n).invalid_since(time.monotonic() - QUIET)])
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
        t_all = time.monotonic()
        pending = set(watch_update)

        def updated():
            """Each PV read until it has advanced once (keeps the Channel Access load low)."""
            pending.difference_update([n for n in list(pending)
                                       if S.read(n)["timestamp"] > stamps[n]])
            return not pending and time.monotonic() - t_all >= hold(sim, mode)
        S.wait_for(updated, WINDOW_LIMIT + hold(sim, mode), interval=0.3,
                   what=lambda: "other devices stopped updating: %s" % sorted(pending))
        RAN.add((sim, mode))
        # "turns INVALID" means: stays INVALID while the fault lasts (HOLD at least). A record
        # that is INVALID only for a moment now and then does not show the fault to a client.
        flicker = [n for n in mine if not steady_invalid(n, t_all)]
        assert flicker == [], "%s %s: listed in the registry, but did not stay INVALID for %g s: %s" % (
            sim, mode, hold(sim, mode), S.describe(flicker))
        same = [n for n in others if reg.pvs[n]["device"] in behind and n not in keep_valid]
        for n in same:
            if steady_invalid(n, t_all):                 # registry gap: fails, but not listed
                UNLISTED.setdefault(n, set()).add("%s %s" % (sim, mode))
        hit = [n for n in others if S.watched(n).invalid_since(f.t0)
               and reg.pvs[n]["device"] not in behind]
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


CASES = [(s, m) for s in SIMS for m in ("silent", "close")]


@pytest.mark.parametrize("sim,mode", CASES)
def test_fault_turns_its_pvs_invalid_and_recovers(sim, mode, live):
    run_fault(sim, mode, live)


def garbage_split(sim):
    """With garbled replies every PV of fails_with turns INVALID, except a record that takes any
    line of text (the NT 20 raw record, role raw, and the internal record it reads): it shows the
    unparsed line without alarm (registry README). Returns (must turn INVALID, must stay valid)."""
    listed = expected(sim, None, "garbage")
    raw_like = [n for n in listed if reg.pvs[n].get("role") == "raw"]
    return [n for n in listed if n not in raw_like], raw_like


@pytest.mark.parametrize("sim", SIMS)
def test_garbage_turns_its_pvs_invalid_and_recovers(sim, live):
    mine, keep = garbage_split(sim)
    run_fault(sim, "garbage", live, mine=mine, keep_valid=keep)
    for n in keep:
        assert S.sevr(n) != S.INVALID, "%s takes any line, it must stay valid: %s" % (
            n, S.describe([n]))


# --- one unit of a bus silent --------------------------------------------------------------------

def polled_units(sim):
    return [u for u in reg.units(sim) if reg.devices_behind(sim, u)]


UNITS = [(s, u) for s in SIMS if len(polled_units(s)) >= 2 for u in polled_units(s)]


@pytest.mark.parametrize("sim,unit", UNITS, ids=["%s:%d" % x for x in UNITS])
def test_one_unit_silent_its_neighbours_keep_answering(sim, unit, live, capsys):
    """Only the PVs of that unit turn INVALID; the neighbours' PVs stay valid and update (with
    each poll of the silent unit waiting for its reply timeout, more slowly: the rate is
    reported)."""
    mine = [n for n in expected(sim, unit) if "%s:%d" % (sim, unit) in reg.pvs[n]["fails_with"]]
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


# --- trip --------------------------------------------------------------------------------------

TRIP_LIMIT = 3.0             # trip -> the status poll shows it (STS and OUT? 1 s, Opta 0.5 s)


def trip_device(sim):
    """The first polled device behind the simulator, and its unit."""
    for u in (reg.units(sim) or [None]):
        for d in reg.devices_behind(sim, u):
            if reg.devices[d]["class"] != "command":
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


def test_registry_fault_lists_name_every_pv_that_fails():
    """The fault tests above check that every PV of the registry's fault list turns INVALID.
    This one checks the other direction: no PV of a faulted device turned INVALID without being
    in the list of that fault (fails_with for silent and garbage, fails_closed for close)."""
    if not RAN:
        pytest.skip("no fault test ran in this session (selected out)")
    unlisted = {n: sorted(s) for n, s in UNLISTED.items()}
    assert unlisted == {}, "turned INVALID, but not in the registry's fault list: %s" % unlisted
