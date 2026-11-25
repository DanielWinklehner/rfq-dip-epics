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
set (the argument of its protocol in OUT), the cathode of the nAIM (signal "on").

The take-over runs under one hold of the lock set (no seq, no delay: checked from the running
IOC), and a client writing through repeated first contacts is never silently swallowed.

The same for the Matsusada supplies (P40, EPICS/Db/supply_first_contact.db): their take-over of
the output state and of the voltage setting has the same structure (checked from the running
IOCs), and a client writing an AU supply's voltage set point through the restart of the rack IOC
never leaves it showing a voltage the supply does not have (setpoint_writer.py; the REK on the
platform IOC rides on the restart in test_09_loop.py)."""
import re
import threading
import time

import pytest

import system as S
from system import reg
from conftest import FIRST_CONTACT, restore_writes, snapshot
from setpoint_writer import SetpointWriter

RACK_IOC = "ioc_rack"
RACK = S.ioc_container(RACK_IOC)
TAKEN = {l["macros"]["REQ"]: l["macros"]["RB"] for d in reg.devices.values() for l in d.get("loads", [])
         if l["db"] == "first_contact.db"}
# Requests of a device, the commands that are sets, per simulator type
SET_HEADS = {"libcom1": ("S", "s"), "edwards_naim": ("!",), "edwards_tic": ("!",)}
# The TIC's requests (tic_control.db, T32): the simulator signal of the device's state, and the
# states in which the request counts as 1 (the read-back's rule)
TIC_STATES = {"turbo:start:set": ("turbo.state", (1, 5, 4)), "backing:start:set": ("backing.state", (1, 4)),
              "on:set": ("g%s.state", (6, 11))}

BACK_LIMIT = 60.0      # s: the IOC's container restarted and its heartbeat counting
TAKE_LIMIT = 5.0       # s after the IOC answers: the valve box and the Opta are polled every 0.5 s,
                       # the gauge every 1 s, the TIC's pumps every 2 s in a chain of seven queries
                       # (about 1 s); the request follows at once (CP link)
SILENT_HOLD = 2.0      # s the requests of a silent device are watched to stay INVALID (4 polls)
LATE_LIMIT = 5.0       # s after the fault is cleared: the reply timeout (1 s) of the poll that
                       # waits, then the next poll (0.5 s)
STAYS = 1.5            # s a request is watched not to follow its read-back (3 polls)
ECHO_LIMIT = 5.0       # as test_03: a read-back after a write
SUPPLY_TAKE_LIMIT = 10.0  # s after the IOC answers: the probe every 1 s, then the echo read by
                       # output:init behind the chain's polls (devtest: taken over within 3 s)


def sim_of(req):
    return reg.sim_of(req)[0]


def tic_signal(req):
    key = next(k for k in TIC_STATES if req.endswith(k))
    signal, states = TIC_STATES[key]
    if "%s" in signal:                                   # the gauge: its socket from the name
        signal = signal % re.search(r":gauge(\d+):", req).group(1)
    return signal, states


def signal_of(req):
    """The simulator signal that holds the device's state for a request."""
    sim = sim_of(req)
    if reg.simulators[sim]["type"] == "edwards_tic":
        return tic_signal(req)[0]
    if reg.simulators[sim]["type"] == "libcom1":
        return re.search(r"com1_setLink\w*\((\w+)\)", S.field(req, "OUT")).group(1)
    assert reg.simulators[sim]["type"] == "edwards_naim", sim
    return "on"


def device_state(req):
    value = int(round(S.sim_value(sim_of(req), signal_of(req))))
    if reg.simulators[sim_of(req)]["type"] == "edwards_tic":
        return int(value in tic_signal(req)[1])
    return value


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
TIC = sorted(n for n in TAKEN if reg.simulators[sim_of(n)]["type"] == "edwards_tic")
VALVES = sorted(n for n in TAKEN if reg.devices[reg.pvs[n]["device"]]["class"] == "valve" and n not in TIC)
PUMPS = sorted(n for n in TAKEN if reg.devices[reg.pvs[n]["device"]]["class"] == "turbo" and n not in TIC)
GAUGES = sorted(n for n in TAKEN if reg.devices[reg.pvs[n]["device"]]["class"] == "gauge" and n not in TIC)
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
PATTERN.update({t: 1 for t in TIC})          # the TIC: both pumps running, the AIM on (as it starts)
WRITE_BEFORE = PUMPS[1]          # pump 2 (not installed in phase 1): written while the Opta is silent


def test_every_request_of_the_list_has_a_take_over():
    """The ten requests of P25 and the gauge: s1 to s8, both pumps, the cathode; and the TIC's
    three (T32): its turbopump, its backing pump, the AIM on its socket 2."""
    assert len(VALVES) == 8 and len(PUMPS) == 2 and len(GAUGES) == 1 and len(TIC) == 3, sorted(TAKEN)
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


# --- the take-over runs under one hold of the lock set (R4) --------------------------------------

TAKE_RECORDS = {"": "calcout", ":on": "dfanout", ":copy": "dfanout", ":off": "dfanout"}
DEFERRING = {"seq", "sseq"}      # run their links in callbacks of their own (seqRecord.c)
DB_FILE = S.REPO / "EPICS" / "Db" / "first_contact.db"


def take_records(req):
    load = next(l for d in reg.devices.values() for l in d.get("loads", [])
                if l["db"] == "first_contact.db" and l["macros"]["REQ"] == req)
    base = "%s:_take:%s" % (load["macros"]["P"], load["macros"]["N"])
    return base, [base + suffix for suffix in TAKE_RECORDS]


def test_no_record_of_the_take_over_defers_its_work():
    """The check and its three steps run in one dbProcess call of _take (first_contact.db,
    header): no record that runs its links from a callback (seq), no delay field set, a chain of
    database links (PP output, forward links) from the check to the end, and the request's
    simulation mode synchronous (SDLY < 0). Read from the running IOC and from the file."""
    text = DB_FILE.read_text()
    types = re.findall(r"^\s*record\(\s*(\w+)", text, re.M)
    assert types and not set(types) & DEFERRING, types
    assert not re.search(r'field\(\s*(DLY\w*|ODLY|SDLY)\s*,\s*"(?!0")[^"]*"', text), "a delay is set in %s" % DB_FILE
    for req in TAKEN:
        base, names = take_records(req)
        found = {n: S.field(n, "RTYP") for n in names}
        assert found == {base + s: t for s, t in TAKE_RECORDS.items()}, found
        assert float(S.field(base, "ODLY")) == 0.0
        assert S.field(base, "OUT").split()[:2] == [base + ":on", "PP"], S.field(base, "OUT")
        assert S.field(base + ":on", "FLNK").split()[0] == base + ":copy"
        assert S.field(base + ":copy", "FLNK").split()[0] == base + ":off"
        assert S.field(base + ":copy", "OUTA").split()[:2] == [req, "PP"]
        assert [S.field(base + s, "OUTA").split()[0] for s in (":on", ":off")] == [req + ".SIMM"] * 2
        assert float(S.field(req, "SDLY")) < 0, "%s: simulation mode asynchronous" % req
        extra = [n for n in reg.pvs if n.startswith(base) and n not in names]
        assert extra == [], extra


# The supplies (supply_first_contact.db): two checks, each with its chain of soft records
SUPPLY_DB = S.REPO / "EPICS" / "Db" / "supply_first_contact.db"
SUPPLY_DBS = [S.REPO / "EPICS" / "Db" / f for f in ("matsusada_au20p7.db", "rek.db")]
SUPPLY_RECORDS = {":_init:otake": "calcout", ":_init:otake:on": "dfanout", ":_init:otake:copy": "dfanout",
                  ":_init:otake:off": "dfanout", ":_init:vtake": "calcout", ":_init:vtake:copy": "dfanout",
                  ":_init:vtake:off": "dfanout"}
SUPPLIES = sorted(d for d, dev in reg.devices.items() if any(l["db"] == "supply_first_contact.db"
                                                             for l in dev.get("loads", [])))
# what output:init (a seq, after the take-over) may still do: none of it is a take-over step
INIT_TAIL = [":voltage:get.PROC", ":_limit:apply.PROC", ":OutputIntlk.DISA", ":OutputIntlk.PROC"]


def supply_prefix(device):
    return next(l["macros"]["S"] for l in reg.devices[device]["loads"] if l["db"] == "supply_first_contact.db")


def link(name, fld):
    """Target and process option of a link field: ("REC.FIELD", "PP"), ("REC", "NPP")."""
    words = S.field(name, fld).split() + ["", ""]
    return words[0], words[1]


def supply_at_rack():
    """An AU supply of the rack IOC with positive voltages (the writer compares magnitudes, but
    a positive one keeps the messages plain)."""
    return next(d for d in SUPPLIES if reg.devices[d]["ioc"] == RACK_IOC
                and float(S.field(reg.role(d, "vset"), "DRVH")) > 0)


def test_every_supply_has_its_first_contact():
    """Every load of matsusada_au20p7.db and rek.db has supply_first_contact.db beside it, with
    the supply's prefix."""
    supplies = sorted(d for d, dev in reg.devices.items()
                      if any(l["db"] in ("matsusada_au20p7.db", "rek.db") for l in dev.get("loads", [])))
    assert supplies == SUPPLIES and len(SUPPLIES) == 5, (supplies, SUPPLIES)
    for d in SUPPLIES:
        assert reg.role(d, "vset") == supply_prefix(d) + ":voltage:setpoint", d


def test_no_record_of_a_supply_take_over_defers_its_work():
    """supply_first_contact.db (header): the check _init:otake and its three steps, and the
    check _init:vtake and its two, each run in one dbProcess call of the check; no seq, no delay
    field set, a chain of database links from the probe's and the echo's forward link to the
    end, the set point's and ToggleOutput's simulation mode synchronous (SDLY < 0). output:init,
    the one seq after the take-over, neither switches a simulation mode nor writes a record a
    client writes. Read from the running IOCs and from the files: the supplies' databases have
    no take-over step of their own any more."""
    text = SUPPLY_DB.read_text()
    types = re.findall(r"^\s*record\(\s*(\w+)", text, re.M)
    assert types and not set(types) & DEFERRING, types
    assert not re.search(r'field\(\s*(DLY\w*|ODLY|SDLY)\s*,\s*"(?!0")[^"]*"', text), "a delay is set in %s" % SUPPLY_DB
    for db in SUPPLY_DBS:
        body = db.read_text()
        seqs = re.findall(r'^\s*record\(\s*seq\s*,\s*"[^"]*?:([^":]+:[^"]+)"', body, re.M)
        assert sorted(seqs) == ["_out:switch", "output:init"], (db.name, seqs)
        assert "_init:vcopy" not in body and "SIMM" not in re.sub(r"#.*", "", body).replace('field(SIMM, "YES")', ""), db.name
    for d in SUPPLIES:
        s = supply_prefix(d)
        names = [s + suffix for suffix in SUPPLY_RECORDS]
        found = {n: S.field(n, "RTYP") for n in names}
        assert found == {s + k: v for k, v in SUPPLY_RECORDS.items()}, found
        for check in (":_init:otake", ":_init:vtake"):
            assert float(S.field(s + check, "ODLY")) == 0.0, s + check
        # the triggers: the forward links of the probe and of the echo
        assert link(s + ":_init:probe", "FLNK")[0] == s + ":_init:otake"
        assert link(s + ":voltage:get", "FLNK")[0] == s + ":_init:vtake"
        # 1. output: check -> on -> copy -> off -> output:init
        assert link(s + ":_init:otake", "OUT") == (s + ":_init:otake:on", "PP")
        assert link(s + ":_init:otake:on", "FLNK")[0] == s + ":_init:otake:copy"
        assert link(s + ":_init:otake:copy", "FLNK")[0] == s + ":_init:otake:off"
        assert link(s + ":_init:otake:off", "FLNK")[0] == s + ":output:init"
        assert [link(s + ":_init:otake:on", f)[0] for f in ("OUTA", "OUTB")] == [s + ":ToggleOutput.SIMM",
                                                                                 s + ":_init:probe.DISA"]
        assert [link(s + ":_init:otake:copy", f) for f in ("OUTA", "OUTB")] == [
            (s + ":ToggleOutput", "PP"), (s + ":SetToggleOutput", "PP")]
        assert link(s + ":_init:otake:copy", "OUTC")[0] == s + ":OutputIntlk.PVAL"
        assert link(s + ":_init:otake:copy", "DOL")[0] == s + ":_init:probe"
        assert link(s + ":_init:otake:off", "OUTA")[0] == s + ":ToggleOutput.SIMM"
        # 2. voltage: check -> copy -> off
        assert link(s + ":_init:vtake", "OUT") == (s + ":_init:vtake:copy", "PP")
        assert link(s + ":_init:vtake:copy", "DOL")[0] == s + ":voltage:get"
        assert link(s + ":_init:vtake:copy", "OUTA") == (s + ":voltage:setpoint", "PP")
        assert link(s + ":_init:vtake:copy", "FLNK")[0] == s + ":_init:vtake:off"
        assert link(s + ":_init:vtake:off", "OUTA")[0] == s + ":voltage:setpoint.SIMM"
        for rec in (":voltage:setpoint", ":ToggleOutput"):
            assert float(S.field(s + rec, "SDLY")) < 0, "%s%s: simulation mode asynchronous" % (s, rec)
        # what comes after: output:init
        tail = [link(s + ":output:init", "LNK%s" % c)[0] for c in "0123456789A"]
        assert [x for x in tail if x] == [s + x for x in INIT_TAIL], tail
        extra = [n for n in reg.pvs if n.startswith(s + ":_init:") and n not in names and n != s + ":_init:probe"]
        assert extra == [], extra


STRESS_PAUSE = 1.0     # s of writes after each take-over before the next restart


@pytest.mark.parametrize("restarts", [1, pytest.param(10, marks=pytest.mark.slow)])
def test_writes_through_the_first_contact_are_sent_or_alarm(restarts, capsys):
    """The rack IOC restarted `restarts` times while a client writes a spare relay (0, 1, 0, ...)
    in a tight loop through each first contact. Every write that returned without error was
    received by the box (its set count went up, the relay has the value) or left the request in
    alarm; SIMM is NO after every take-over and at the end. "Returned without error" is: put
    completed, the record read right after by the same IOC (heartbeat not reset); a write that the
    stopping IOC's disconnection completed is counted apart, it can neither be confirmed nor fail. The race this is about (a write
    inside the take-over) cannot be hit on purpose; the default run restarts once, the slow one
    ten times: make -C emulation test ARGS='-m slow emulation/tests/test_11_first_contact.py'.
    At the same time a second client writes the voltage set point of an AU supply (P40,
    setpoint_writer.py): with SIMM NO and no write in flight, the set point always shows the
    supply's setting, and at the end SIMM is NO and set point, echo and simulator agree."""
    import epics
    from mist2sim.control import ControlClient
    req = SPARE[3]
    sim, signal = sim_of(req), signal_of(req)
    host, port = reg.simulators[sim]["host"], reg.simulators[sim]["control_port"]
    results, stop = [], threading.Event()

    def writer():
        pv = epics.PV(req, form="time", auto_monitor=False)
        beat = epics.PV(hb, auto_monitor=False)
        ctl = ControlClient(host, port, timeout=5.0)
        value = 1
        while not stop.is_set():
            if not pv.connected:
                time.sleep(0.005)
                continue
            try:
                sent = ctl.stats()["heads"].get("S", 0)
                before = beat.get(use_monitor=False, timeout=1.0)
                ok = pv.put(value, wait=True, timeout=2.0)
                d = pv.get_with_metadata(use_monitor=False, form="time", timeout=1.0)
                after = beat.get(use_monitor=False, timeout=1.0)
                delta = ctl.stats()["heads"].get("S", 0) - sent
                state = int(round(ctl.get(signal)["value"]))
                if ok != 1 or d is None or before is None or after is None or after < before:
                    # not confirmed by the IOC that took it: pyepics reports a put that the
                    # disconnection completed (ECA_DISCONN) as done (epics/ca.py, _onPutEvent
                    # ignores the status), so a write into the stopping IOC counts here
                    results.append(("unconfirmed", value, ok, delta, state))
                else:
                    results.append(("ok", value, d["severity"], delta, state))
                value = 1 - value
            except Exception as exc:                    # noqa: BLE001  the IOC goes away
                results.append(("error", value, repr(exc)))
                time.sleep(0.01)
        ctl.close()

    hb = reg.iocs[RACK_IOC]["roles"]["heartbeat"]
    thread = epics.ca.CAThread(target=writer, daemon=True)
    voltage = SetpointWriter(supply_at_rack())
    thread.start()
    simm = []
    try:
        with voltage:
            for _ in range(restarts):
                voltage.silence()
                S.container("restart", RACK)
                S.wait_for(lambda: S.connected(hb) and S.get(hb) >= 1, BACK_LIMIT, "the rack IOC up again")
                S.wait_for(lambda: S.sevr(TAKEN[req]) != S.INVALID, TAKE_LIMIT, "the box answers")
                time.sleep(STRESS_PAUSE)
                voltage.answer_after_writes()
                voltage.wait_taken_over(SUPPLY_TAKE_LIMIT)
                simm.append({n: S.field(n, "SIMM") for n in TAKEN})
    finally:
        stop.set()
        thread.join(10)
    ok = [r for r in results if r[0] == "ok"]
    bad = [r for r in ok if not (r[2] == S.INVALID or (r[2] == S.NO_ALARM and r[3] >= 1 and r[4] == r[1]))]
    S.report("first contact under writes: %d restarts, %d writes confirmed by the IOC (%d in alarm), %d not "
             "confirmed while the IOC restarted (%d of them reached the box)" % (
                 restarts, len(ok), sum(1 for r in ok if r[2] == S.INVALID), len(results) - len(ok),
                 sum(1 for r in results if r[0] == "unconfirmed" and r[3] >= 1)), capsys)
    assert ok, "no write completed"
    assert bad == [], "accepted without reaching the box (value, severity, sets, relay): %s" % bad[:5]
    assert all(set(s.values()) == {"NO"} for s in simm), simm
    S.put(req, 0)
    S.wait_for(lambda: device_state(req) == 0 and S.sevr(req) == S.NO_ALARM, ECHO_LIMIT, S.describe([req]))
    assert {n: S.field(n, "SIMM") for n in TAKEN} == {n: "NO" for n in TAKEN}
    S.report(voltage.summary(), capsys)
    assert voltage.problems() == [], voltage.problems()


@pytest.mark.slow
def test_a_supply_set_point_written_through_ten_restarts_of_its_ioc(capsys):
    """P40 for the supply on the other IOC (the REK, platform IOC) with ten restarts; the default
    run has one, in test_09_loop.py. make -C emulation test ARGS='-m slow
    emulation/tests/test_11_first_contact.py'"""
    device = next(d for d in SUPPLIES if reg.devices[d]["ioc"] != RACK_IOC)
    ioc = reg.devices[device]["ioc"]
    hb = reg.iocs[ioc]["roles"]["heartbeat"]
    voltage = SetpointWriter(device)
    with voltage:
        for _ in range(10):
            voltage.silence()
            S.container("restart", S.ioc_container(ioc))
            S.wait_for(lambda: S.connected(hb) and S.get(hb) >= 1, BACK_LIMIT, "%s up again" % ioc)
            voltage.answer_after_writes()
            voltage.wait_taken_over(SUPPLY_TAKE_LIMIT)
    S.report(voltage.summary(), capsys)
    gates = [g for g in (reg.gate_record(d) for d in reg.devices) if g and reg.pvs[g]["ioc"] == ioc]
    S.wait_for(lambda: all(S.field(g, "DISA") == "0" for g in gates), FIRST_CONTACT, "gates enabled")
    assert voltage.problems() == [], voltage.problems()
