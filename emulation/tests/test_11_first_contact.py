"""First contact (P25, EPICS/Db/first_contact.db): after a start of the rack IOC each request of a
valve, a turbopump and the ion gauge takes over the state of its device at the device's first
answer, with NO_ALARM, and nothing is sent to the device for it. A device that does not answer
leaves its requests INVALID (UDF) until it answers. A client's write before the take-over is
sent as before and stays. Afterwards the requests behave as before: writes are acknowledged, a
rejected or unanswered set alarms, the read-back never overwrites the request. SIMM is NO in each
of these cases.

One restart of the rack IOC serves every check (module fixture `restart`): the valves set to a
pattern (foreline valve open, vent valve closed, one bo and one ao channel energised), turbopump
1 running, the gauge on, and the turbopump Opta silent at the start; the valve box and the gauge
answer at once, the Opta only when its fault is cleared.

The request records and their read-backs come from the registry: every load of first_contact.db
(macros REQ and RB). The device's state is read from the simulator: the channel of a libcom1
set (the argument of its protocol in OUT), the cathode of the nAIM (signal "on")."""
import re
import time

import pytest

import system as S
from system import reg
from conftest import FIRST_CONTACT, restore_writes, snapshot

RACK_IOC = "ioc_rack"
RACK = S.ioc_container(RACK_IOC)
TAKEN = {l["macros"]["REQ"]: l["macros"]["RB"] for d in reg.devices.values() for l in d.get("loads", [])
         if l["db"] == "first_contact.db"}
# Requests of a device, the commands that are sets, per simulator type
SET_HEADS = {"libcom1": ("S", "s"), "edwards_naim": ("!",)}

BACK_LIMIT = 60.0      # s: the IOC's container restarted and its heartbeat counting
TAKE_LIMIT = 3.0       # s after the IOC answers: the valve box and the Opta are polled every 0.5 s,
                       # the gauge every 1 s; the request follows at once (CP link)
SILENT_HOLD = 2.0      # s the requests of a silent device are watched to stay INVALID (4 polls)
LATE_LIMIT = 5.0       # s after the fault is cleared: the reply timeout (1 s) of the poll that
                       # waits, then the next poll (0.5 s)
STAYS = 1.5            # s a request is watched not to follow its read-back (3 polls)
ECHO_LIMIT = 5.0       # as test_03: a read-back after a write


def sim_of(req):
    return reg.sim_of(req)[0]


def signal_of(req):
    """The simulator signal that holds the device's state for a request."""
    sim = sim_of(req)
    if reg.simulators[sim]["type"] == "libcom1":
        return re.search(r"com1_setLink\w*\((\w+)\)", S.field(req, "OUT")).group(1)
    assert reg.simulators[sim]["type"] == "edwards_naim", sim
    return "on"


def device_state(req):
    return int(round(S.sim_value(sim_of(req), signal_of(req))))


def sets_received(sim):
    heads = S.control(sim).stats()["heads"]
    return sum(heads.get(h, 0) for h in SET_HEADS[reg.simulators[sim]["type"]])


def until(cond, timeout, interval=0.1):
    """True as soon as cond() holds, False after timeout (does not fail: the fixture records)."""
    end = time.monotonic() + timeout
    while True:
        try:
            if cond():
                return True
        except Exception:                     # noqa: BLE001  an IOC that restarts does not answer
            pass
        if time.monotonic() > end:
            return False
        time.sleep(interval)


def state_of(names):
    """Value, severity, status and SIMM of each request, as read now."""
    out = {}
    for n in names:
        d = S.read(n)
        out[n] = dict(value=int(round(d["value"])), severity=d["severity"], status=d["status"],
                      simm=S.field(n, "SIMM"))
    return out


def show(states):
    return ", ".join("%s=%s %s/%s SIMM %s" % (n, s["value"], S.SEVERITY[s["severity"]], S.STATUS[s["status"]],
                                               s["simm"]) for n, s in states.items())


# The requests by simulator, and the pattern written before the restart
VALVES = sorted(n for n in TAKEN if reg.devices[reg.pvs[n]["device"]]["class"] == "valve")
PUMPS = sorted(n for n in TAKEN if reg.devices[reg.pvs[n]["device"]]["class"] == "turbo")
GAUGES = sorted(n for n in TAKEN if reg.devices[reg.pvs[n]["device"]]["class"] == "gauge")
SILENT_SIM = sim_of(PUMPS[0])                       # the Opta: silent at the IOC's start
SILENT = sorted(n for n in TAKEN if sim_of(n) == SILENT_SIM)
ANSWERING = sorted(n for n in TAKEN if sim_of(n) != SILENT_SIM)
VALVE_DEVICE = reg.pvs[VALVES[0]]["device"]
CHANNELS = reg.devices[VALVE_DEVICE]["channels"]


def channel_cmd(label):
    return next(c["roles"]["cmd"] for c in CHANNELS.values() if c.get("label") == label)


FORELINE, VENT = channel_cmd("Foreline Valve"), channel_cmd("Vent Valve")
OTHER_BO = next(c["roles"]["cmd"] for c in CHANNELS.values() if c.get("spare") is None
                and reg.pvs[c["roles"]["cmd"]]["type"] == "bo" and c["roles"]["cmd"] not in (FORELINE, VENT))
SPARE = sorted(c["roles"]["cmd"] for c in CHANNELS.values() if c.get("spare"))
SPARE_AO, WRITTEN_AO, HELD_AO = SPARE[0], SPARE[1], SPARE[2]  # ao channels s5..s8
PATTERN = {n: 0 for n in TAKEN}
PATTERN.update({FORELINE: 1, VENT: 0, OTHER_BO: 1, SPARE_AO: 1, PUMPS[0]: 1, PUMPS[1]: 0})
PATTERN.update({g: 1 for g in GAUGES})
WRITE_BEFORE = PUMPS[1]          # pump 2 (not installed in phase 1): written while the Opta is silent


def test_every_request_of_the_list_has_a_take_over():
    """The ten requests of P25 and the gauge: s1 to s8, both pumps, the cathode."""
    assert len(VALVES) == 8 and len(PUMPS) == 2 and len(GAUGES) == 1, sorted(TAKEN)
    for req, rb in TAKEN.items():
        assert reg.pvs[req]["access"] == "w" and rb in reg.pvs, (req, rb)
    assert reg.pvs[SPARE_AO]["type"] == "ao" and reg.pvs[OTHER_BO]["type"] == "bo"


@pytest.fixture(scope="module")
def restart():
    """The pattern written, the Opta silent, the rack IOC restarted; what each phase showed."""
    obs = {}
    try:
        for n, v in PATTERN.items():
            S.put(n, v)
        S.wait_for(lambda: all(device_state(n) == v for n, v in PATTERN.items()), ECHO_LIMIT,
                   lambda: "the pattern in the devices: %s" % {n: device_state(n) for n in PATTERN})
        S.wait_for(lambda: all(S.get(TAKEN[n]) == v for n, v in PATTERN.items() if n not in GAUGES),
                   ECHO_LIMIT, lambda: "read-backs of the pattern: %s" % S.describe(list(TAKEN.values())))
        obs["before"] = {n: device_state(n) for n in TAKEN}
        S.control(SILENT_SIM).fault("silent")
        for sim in {sim_of(n) for n in TAKEN}:
            S.control(sim).stats(reset=True)
        S.container("restart", RACK)
        hb = reg.iocs[RACK_IOC]["roles"]["heartbeat"]
        S.wait_for(lambda: S.connected(hb) and S.get(hb) >= 1, BACK_LIMIT, "the rack IOC up again")
        t_up = time.monotonic()
        obs["took_early"] = None
        if until(lambda: all(S.sevr(n) == S.NO_ALARM for n in ANSWERING), TAKE_LIMIT):
            obs["took_early"] = time.monotonic() - t_up
        obs["early"] = state_of(TAKEN)
        obs["sets_early"] = {sim: sets_received(sim) for sim in {sim_of(n) for n in TAKEN}}
        # the silent device: its requests stay INVALID, watched for SILENT_HOLD
        seen = []
        end = time.monotonic() + SILENT_HOLD
        while time.monotonic() < end:
            seen.append(state_of(SILENT))
            time.sleep(0.25)
        obs["silent"] = seen
        # a client's write before the take-over: sent (the Opta counts it), unanswered as today
        S.put(WRITE_BEFORE, 1)
        obs["written"] = state_of([WRITE_BEFORE])[WRITE_BEFORE]
        obs["sets_written"] = sets_received(SILENT_SIM)
        S.control(SILENT_SIM).clear("silent")
        t_clear = time.monotonic()
        obs["took_late"] = None
        late = [n for n in SILENT if n != WRITE_BEFORE]
        if until(lambda: all(S.sevr(n) == S.NO_ALARM for n in late), LATE_LIMIT):
            obs["took_late"] = time.monotonic() - t_clear
        S.wait_for(lambda: S.sevr(TAKEN[WRITE_BEFORE]) != S.INVALID, LATE_LIMIT,
                   lambda: "read-back of %s valid after the fault: %s" % (WRITE_BEFORE, S.describe([TAKEN[WRITE_BEFORE]])))
        time.sleep(STAYS)
        obs["late"] = state_of(TAKEN)
        obs["sets_late"] = {sim: sets_received(sim) for sim in {sim_of(n) for n in TAKEN}}
        obs["after"] = {n: device_state(n) for n in TAKEN}
        yield obs
    finally:
        problems = S.clear_everything()
        restore_writes([n for n in TAKEN if n in snapshot])
        gates = [g for g in (reg.gate_record(d) for d in reg.devices) if g and reg.pvs[g]["ioc"] == RACK_IOC]
        S.wait_for(lambda: all(S.field(g, "DISA") == "0" for g in gates), FIRST_CONTACT,
                   "gate records of the rack IOC enabled (first contact)")
        assert not problems, problems


def test_requests_take_over_the_device_state_with_no_alarm(restart, capsys):
    """The valves and the gauge at once, the pumps when the Opta answers."""
    early = {n: s for n, s in restart["early"].items() if n in ANSWERING}
    assert restart["took_early"] is not None, "not taken over within %g s: %s" % (TAKE_LIMIT, show(early))
    late = {n: s for n, s in restart["late"].items() if n in SILENT and n != WRITE_BEFORE}
    assert restart["took_late"] is not None, "not taken over within %g s of the answer: %s" % (LATE_LIMIT, show(late))
    for states in (early, late):
        wrong = {n: s for n, s in states.items() if s["severity"] != S.NO_ALARM or s["value"] != restart["before"][n]}
        assert wrong == {}, "device state %s, requests %s" % (restart["before"], show(wrong))
    S.report("first contact: %d requests taken over %.1f s after the IOC answered, %d %.1f s after their "
             "device answered (limits %g s, %g s)" % (len(early), restart["took_early"], len(late),
                                                       restart["took_late"], TAKE_LIMIT, LATE_LIMIT), capsys)


def test_nothing_is_sent_and_the_devices_keep_their_state(restart):
    """No set command reached a simulator from the IOC's start to the first client write, and
    afterwards only that write (to the silent Opta, which did not execute it)."""
    assert restart["sets_early"] == {sim: 0 for sim in restart["sets_early"]}, restart["sets_early"]
    expected = {sim: (1 if sim == SILENT_SIM else 0) for sim in restart["sets_late"]}
    assert restart["sets_late"] == expected, restart["sets_late"]
    assert restart["after"] == restart["before"], (restart["before"], restart["after"])
    assert restart["before"][FORELINE] == 1 and restart["before"][VENT] == 0
    assert restart["before"][PUMPS[0]] == 1 and all(restart["before"][g] == 1 for g in GAUGES)


def test_a_silent_device_leaves_its_requests_invalid_until_it_answers(restart):
    early = {n: restart["early"][n] for n in SILENT}
    bad = [show(s) for s in restart["silent"] + [early]
           if any(v["severity"] != S.INVALID or v["status"] != S.UDF for v in s.values())]
    assert bad == [], "a request of the silent %s not INVALID/UDF: %s" % (SILENT_SIM, bad[:2])
    assert restart["took_late"] is not None, show({n: restart["late"][n] for n in SILENT})


def test_a_write_before_the_take_over_is_sent_and_stays(restart):
    """Sent as before (the Opta counted the set; it was silent, so the record alarms as today),
    and the request keeps the client's value when the device answers: no take-over after it."""
    assert restart["sets_written"] == 1, restart["sets_written"]
    assert restart["written"]["value"] == 1 and restart["written"]["severity"] == S.INVALID, restart["written"]
    late = restart["late"][WRITE_BEFORE]
    assert restart["after"][WRITE_BEFORE] == 0, "the silent Opta executed the set"
    assert late["value"] == 1 and late["status"] != S.UDF, "taken over after the client's write: %s" % late
    assert S.get(TAKEN[WRITE_BEFORE]) == 0                  # the read-back shows the relay
    S.put(WRITE_BEFORE, 0)                                  # the next write is sent and acknowledged
    assert S.sevr(WRITE_BEFORE) == S.NO_ALARM, S.describe([WRITE_BEFORE])


def test_simulation_mode_is_off_in_every_case(restart):
    """After the take-over (valves, gauge), without contact (pumps), after a late contact, after
    a client's write before the take-over, and now."""
    phases = {"early": restart["early"], "late": restart["late"], "written": {WRITE_BEFORE: restart["written"]}}
    phases.update({"silent %d" % i: s for i, s in enumerate(restart["silent"])})
    bad = {p: {n: s["simm"] for n, s in states.items() if s["simm"] != "NO"} for p, states in phases.items()}
    assert {p: b for p, b in bad.items() if b} == {}
    now = {n: S.field(n, "SIMM") for n in TAKEN}
    assert set(now.values()) == {"NO"}, now


def test_after_the_take_over_writes_and_alarms_are_as_before(restart):
    """An acknowledged write (a bo and an ao channel), an unanswered one (silent box) and a
    rejected one (the gauge answers an error code) alarm on the request and are not executed."""
    for n in (OTHER_BO, WRITTEN_AO):
        target = 1 - device_state(n)
        S.put(n, target)
        assert S.sevr(n) == S.NO_ALARM, S.describe([n])
        S.wait_for(lambda: S.get(TAKEN[n]) == target and device_state(n) == target, ECHO_LIMIT,
                   lambda: "%s follows: %s" % (n, S.describe([TAKEN[n]])))
    box = sim_of(WRITTEN_AO)
    before = device_state(WRITTEN_AO)
    with S.fault(box, "silent"):
        S.put(WRITTEN_AO, 1 - before)
        assert S.sevr(WRITTEN_AO) == S.INVALID, S.describe([WRITTEN_AO])
    assert device_state(WRITTEN_AO) == before, "the silent box executed the set"
    S.put(WRITTEN_AO, before)
    assert S.sevr(WRITTEN_AO) == S.NO_ALARM, S.describe([WRITTEN_AO])
    gauge = GAUGES[0]
    S.sim_set(sim_of(gauge), "reject", 4)
    try:
        S.put(gauge, 1)
        assert S.sevr(gauge) == S.INVALID, "a rejected command ends without alarm: %s" % S.describe([gauge])
    finally:
        S.sim_release(sim_of(gauge), "reject")
    S.put(gauge, 1)
    assert S.sevr(gauge) == S.NO_ALARM and device_state(gauge) == 1, S.describe([gauge])
    assert {n: S.field(n, "SIMM") for n in TAKEN} == {n: "NO" for n in TAKEN}


def test_a_later_change_of_the_read_back_does_not_change_the_request(restart):
    """The relay of a channel changes in the box (held by the simulator), the cathode goes off in
    the gauge: the read-backs follow, the requests keep what was written."""
    req, rb = HELD_AO, TAKEN[HELD_AO]
    value = int(S.get(req))
    S.sim_set(sim_of(req), signal_of(req), 1 - value)
    gauge = GAUGES[0]
    S.sim_set(sim_of(gauge), "on", 0)
    try:
        S.wait_for(lambda: S.get(rb) == 1 - value, ECHO_LIMIT, lambda: "read-back follows: %s" % S.describe([rb]))
        S.wait_for(lambda: S.get(TAKEN[gauge]) == 0, ECHO_LIMIT,
                   lambda: "cathode state follows: %s" % S.describe([TAKEN[gauge]]))
        time.sleep(STAYS)
        assert (S.get(req), S.sevr(req)) == (value, S.NO_ALARM), S.describe([req])
        assert (S.get(gauge), S.sevr(gauge)) == (1, S.NO_ALARM), S.describe([gauge])
    finally:
        S.sim_release(sim_of(req), signal_of(req))
        S.sim_release(sim_of(gauge), "on")
