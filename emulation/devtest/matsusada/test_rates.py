"""Bus timing: PRIO=HIGH of the set points, update rates of the monitors (report), IOC log."""
import os
import re
import statistics
import time

import epics
import pytest

from mat import BUILD, GRACE, control, get, put, wait_for

BAUD, BITS = 9600, 10
REPLY_TIMEOUT = 0.150        # matsusada_co_ctrl.proto
OVERHEAD = 0.0015            # line idle per protocol (IOC, asyn, TCP); fitted, the report shows
                             # the idle time measured per transaction
CHAINS = {"mat_opt": [1, 2], "mat_co": [3, 5]}
LENS3_SCANS = {"voltage:read": ".1 second", "current:read": ".1 second",
               "status:read": "1 second", "voltage:get": "5 second",
               "read_output_status": "5 second"}


# --- bus arithmetic ------------------------------------------------------------------------------

def tx(request, reply, turnaround_ms, dead=False):
    """Seconds one transaction holds the line: characters at 9600 baud (CR included) plus the
    turnaround when there is a reply; a dead unit holds it for the reply timeout instead."""
    t = (len(request) + 1) * BITS / BAUD
    if reply is None:
        return t
    if dead:
        return t + REPLY_TIMEOUT
    return t + (len(reply) + 1) * BITS / BAUD + turnaround_ms / 1000.0


def protocols(unit, ta, dead=False, overhead=0.0):
    """The protocols the database runs for one polled unit: (period s, seconds, name)."""
    u = "#%d " % unit
    return [(p, t + overhead, n) for p, t, n in [
        (0.1, tx(u + "MN1", "MONI1=FFFH", ta, dead), "MN1"),
        (0.1, tx(u + "MN2", "MONI2=FFFH", ta, dead), "MN2"),
        (1.0, tx(u + "REN", None, ta) + tx(u + "STS", "#%d CO RM" % unit, ta, dead), "STS"),
        (5.0, tx(u + "CH0?", "CH0=FFFFH", ta, dead), "CH0?"),
        (5.0, tx(u + "SW?", "SW1", ta, dead) + tx(u + "CH1?", "CH1=FFFFH", ta, dead), "SW?"),
    ]]


def bus_rate(units, ta, dead=()):
    """Continuous bus arithmetic: monitors at 10 Hz unless the line is full; then they share
    what the other protocols leave. Returns {unit: rate} (the same for every unit)."""
    fixed = sum(t / p for u in units for p, t, n in protocols(u, ta, u in dead) if p > 0.1)
    mon = sum(t for u in units for p, t, n in protocols(u, ta, u in dead) if p == 0.1)
    rate = min(10.0, (1.0 - fixed) / mon)
    return {u: rate for u in units}


def scan_model(units, ta, dead=(), seconds=120.0):
    """The same with the EPICS scan rules: at every tick of its scan period a record that is not
    busy is queued (a busy record misses the tick); the line serves the queue in the order of the
    scan list (the order the records were loaded), with OVERHEAD between two protocols.
    Returns {(unit, "MN1" or "MN2"): rate}."""
    recs = [dict(unit=u, period=p, t=t, name=n, busy=False, done=0)
            for u in units for p, t, n in protocols(u, ta, u in dead, OVERHEAD)]
    phase = {0.1: 0.0, 1.0: 0.031, 5.0: 0.017}
    ticks = sorted((phase[r["period"]] + k * r["period"], i) for i, r in enumerate(recs)
                   for k in range(int(seconds / r["period"])))
    queue, current, k = [], None, 0                 # current: (finish time, record index)
    while k < len(ticks):
        tick, i = ticks[k]
        if current and current[0] <= tick:          # the transaction on the line ends first
            finish, j = current
            recs[j]["busy"] = False
            recs[j]["done"] += 1
            current = None
            if queue:
                j = queue.pop(0)
                current = (finish + recs[j]["t"], j)
            continue
        k += 1
        if not recs[i]["busy"]:
            recs[i]["busy"] = True
            if current:
                queue.append(i)
            else:
                current = (tick + recs[i]["t"], i)
    return {(r["unit"], r["name"]): r["done"] / seconds for r in recs if r["period"] == 0.1}


# --- measurement ---------------------------------------------------------------------------------

def measure(units_by_chain, seconds=10.0):
    """Monitor update rates: {(unit, "MN1"|"MN2"): rate} seen by a Channel Access client
    (voltage:read and current:read, MDEL -1 for the measurement, so that every processing is
    posted), and {unit: (MN1 + MN2) / 2} from the simulator's transaction counts."""
    pvs = {(u, n): "AU-20P7-%d:%s" % (u, s) for us in units_by_chain.values() for u in us
           for n, s in (("MN1", "voltage:read"), ("MN2", "current:read"))}
    counts = {k: 0 for k in pvs}
    monitors = []
    for k, pv in pvs.items():
        put(pv + ".MDEL", -1)
        m = epics.PV(pv, callback=lambda k=k, **kw: counts.__setitem__(k, counts[k] + 1))
        m.wait_for_connection(3)
        monitors.append(m)
    time.sleep(1.0)
    for c in counts:
        counts[c] = 0
    ctls = {ch: control(ch) for ch in units_by_chain}
    for c in ctls.values():
        c.stats(reset=True)
    time.sleep(seconds)
    stats = {ch: c.stats() for ch, c in ctls.items()}
    ca = {k: n / seconds for k, n in counts.items()}
    for m in monitors:
        m.clear_callbacks()
        m.disconnect()
    for pv in pvs.values():
        put(pv + ".MDEL", 0)
    sim = {}
    for ch, units in units_by_chain.items():
        s = stats[ch]
        sim[ch] = (s["elapsed_s"] - s["busy_s"]) / max(1, s["requests"])   # idle per request
        for u in units:
            replies = s["per_unit"].get(str(u), {}).get("replies", 0) / s["elapsed_s"]
            sim[u] = (replies - 1.0 - 3 / 5.0) / 2      # minus STS 1/s, CH0? SW? CH1? per 5 s
    for c in ctls.values():
        c.close()
    return sim, ca


def set_turnaround(ms):
    for ch in CHAINS:
        with control(ch) as c:
            if ms is None:
                c.release("line.turnaround_ms")
            else:
                c.set("line.turnaround_ms", ms)


def poll_lens3(on):
    for s, scan in LENS3_SCANS.items():
        put("AU-20P7-4:%s.SCAN" % s, scan if on else "Passive")


@pytest.fixture(autouse=True)
def after_grace():
    """Writes to the set points are sent only after the GRACE period of the database."""
    wait_for(lambda: get("DEVTEST:heartbeat") >= GRACE + 1, 15, "IOC past GRACE")


# --- tests ---------------------------------------------------------------------------------------

def latency_of_sets(pv, unit, n=20):
    """Seconds from a caput of a voltage set point to the arrival of CH0 at the simulator, while
    the chain is polled as usual."""
    out = []
    with control("mat_co") as c:
        for i in range(n):
            volts = 1000.0 + 37 * i
            t0 = time.monotonic()
            epics.caput(pv, volts, wait=False)
            while abs(c.get("%d.vset" % unit)["target"] - volts) > 0.5:
                if time.monotonic() - t0 > 2:
                    pytest.fail("set did not arrive")
            out.append(time.monotonic() - t0)
            time.sleep(0.11 + 0.013 * (i % 7))      # different phases of the polling
    return out


def test_prio_high_overtakes_the_polls(capsys):
    pv = "AU-20P7-3:voltage:setpoint"
    for d in ("AU-20P7-3", "AU-20P7-5"):            # both supplies of the chain on, polled
        if get(d + ":SetToggleOutput") == 0:
            put(d + ":SetToggleOutput", 1)
    high = latency_of_sets(pv, 3)
    put(pv + ".PRIO", "LOW")
    try:
        low = latency_of_sets(pv, 3)
    finally:
        put(pv + ".PRIO", "HIGH")
    lines = ["PRIO of AU-20P7-3:voltage:setpoint, caput -> CH0 at the simulator, chain mat_co "
             "polled (units 3 and 5), %d sets each:" % len(high)]
    for name, v in (("HIGH", high), ("LOW ", low)):
        lines.append("  %s  median %5.1f ms   max %5.1f ms" % (
            name, statistics.median(v) * 1000, max(v) * 1000))
    report("\n".join(lines), capsys)
    assert statistics.median(high) < 0.025
    assert statistics.median(high) < statistics.median(low) / 2


def test_rate_report(capsys):
    """Five supplies as in the table, lens 3 loaded but not polled; then lens 3 polled."""
    for d in ("AU-20P7-1", "AU-20P7-2", "AU-20P7-3", "AU-20P7-5"):
        if get(d + ":SetToggleOutput") == 0:
            put(d + ":SetToggleOutput", 1)
    with control("mat_co") as c:
        ta = c.info()["settings"]["turnaround_ms"]
    rows = []
    cases = [("turnaround %g ms (configuration)" % ta, ta, False),
             ("turnaround 16 ms", 16.0, False),
             ("turnaround %g ms, lens 3 polled" % ta, ta, True),
             ("turnaround 16 ms, lens 3 polled", 16.0, True)]
    try:
        for label, t, lens3 in cases:
            set_turnaround(None if t == ta else t)
            poll_lens3(lens3)
            chains = {"mat_opt": [1, 2], "mat_co": [3, 5] + ([4] if lens3 else [])}
            time.sleep(1.0)
            sim, ca = measure(chains)
            for ch, units in chains.items():
                bus, model = bus_rate(units, t), scan_model(units, t)
                for u in units:
                    rows.append(dict(case=label, chain=ch, unit=u, bus=bus[u], idle=sim[ch],
                                     sv=model[u, "MN1"], si=model[u, "MN2"], sim=sim[u],
                                     cv=ca[u, "MN1"], ci=ca[u, "MN2"]))
    finally:
        set_turnaround(None)
        poll_lens3(False)
    lines = ["Update rate of the monitor PVs, Hz. Predicted: bus = bus arithmetic (the line shared",
             "evenly), scan V/I = the same line with the EPICS scan rules (a busy record misses its",
             "tick; the queue is served in scan-list order). Measured: CA V/I = monitor updates of",
             "voltage:read / current:read seen by a Channel Access client, sim = (MN1 + MN2) / 2 from",
             "the simulator's transaction counts; idle = line idle time per request (sim stats).",
             "The scan model counts %.1f ms between two protocols." % (OVERHEAD * 1000),
             "%-32s %-7s %4s | %5s %6s %6s | %6s %6s %6s | %6s %7s" % (
                 "case", "chain", "unit", "bus", "scan V", "scan I", "CA V", "CA I", "sim",
                 "CA/bus", "idle ms")]
    for r in rows:
        lines.append("%-32s %-7s %4d | %5.2f %6.2f %6.2f | %6.2f %6.2f %6.2f | %5.0f%% %7.1f" % (
            r["case"], r["chain"], r["unit"], r["bus"], r["sv"], r["si"], r["cv"], r["ci"],
            r["sim"], 100 * (r["cv"] + r["ci"]) / 2 / r["bus"], r["idle"] * 1000))
    report("\n".join(lines), capsys)
    for r in rows:
        assert (r["cv"] + r["ci"]) / 2 == pytest.approx(r["sim"], rel=0.1), r  # every poll seen
        assert r["cv"] == pytest.approx(r["sv"], rel=0.15, abs=0.3), r      # the scan model
        assert r["ci"] == pytest.approx(r["si"], rel=0.15, abs=0.3), r      # explains the rates


def test_rate_with_a_silent_neighbour(capsys):
    put("AU-20P7-3:SetToggleOutput", 1)
    with control("mat_co") as c:
        c.fault("silent", unit=5)
        try:
            time.sleep(1.5)
            sim, ca = measure({"mat_co": [3]})
        finally:
            c.clear("silent")
    model = scan_model([3, 5], 5.0, dead=(5,))[3, "MN1"]
    bus = bus_rate([3, 5], 5.0, dead=(5,))[3]
    report("Unit 5 silent (reply timeout %d ms): unit 3 keeps %.2f updates/s (CA, voltage:read), "
           "%.2f (sim); predicted: scan model %.2f, bus arithmetic %.2f"
           % (REPLY_TIMEOUT * 1000, ca[3, "MN1"], sim[3], model, bus), capsys)
    assert ca[3, "MN1"] > 2.0
    wait_for(lambda: get("AU-20P7-5:voltage:read.SEVR") == 0, 5, "unit 5 back")


# Lines of the IOC log that mean an error (as in devtest/example). StreamDevice's messages about
# the traffic (no reply, mismatch, disconnected) are not database, protocol or link errors: the
# faults of this case cause them on purpose, and the functional tests check their effect. They
# are counted per port in the report.
ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad |mismatch|does not match|too short|no match|disconnected"
                   r"|no reply|timeout|not connected", re.I)
TRAFFIC = re.compile(r"^\S+ \S+ (?P<port>\S+) (\S+:? )?(No reply within \d+ ms|\d+ additional errors|"
                     r"device \S+ 0 disconnected|lockRequest: |Input \"[^\"]*\"|mismatch after|"
                     r"got \"|No match for |Input \"[0-9A-F]+H\" does not match format \"%=04X\")")


def test_ioc_log_has_no_error_line(capsys):
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    assert any("iocRun: All initialization complete" in l for l in lines)
    errors = [l for l in lines if ERROR.search(l) and not l.startswith("on error ")
              and not TRAFFIC.search(l)]
    assert errors == []
    ports = {}
    for l in lines:
        m = TRAFFIC.search(l)
        if m:
            ports[m.group("port")] = ports.get(m.group("port"), 0) + 1
    report("IOC log: no database, protocol or link error; StreamDevice traffic messages per "
           "port (from the faults): %s" % (ports or "none"), capsys)


def report(text, capsys):
    with open(os.path.join(BUILD, "rate_report.txt"), "a") as f:
        f.write(text + "\n\n")
    with capsys.disabled():
        print("\n" + text)
