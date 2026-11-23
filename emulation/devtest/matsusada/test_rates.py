"""Bus timing: PRIO=HIGH of the set points, update rates of the polls (report), IOC log."""
import os
import re
import statistics
import time

import epics
import pytest

from mat import BUILD, GRACE, control, get, put, wait_for

BAUD, BITS = 9600, 10
REPLY_TIMEOUT = 0.150 + 0.050  # matsusada_co_ctrl.proto: ReplyTimeout, then the @replytimeout wait
CHAINS = {"mat_opt": [1, 2], "mat_co": [3, 4]}


# Task T22: the state reads (CH0?, SW?, CH1?) begin with a status check (STS), which the
# simulator counts among the unit's replies. True if the protocol file the IOC loads has it.
STATUS_CHECK = '"#\\$1 STS"' in re.search(
    r"\nget_voltage\s*\{([^}]*)\}", open("/repo/EPICS/Db/matsusada_co_ctrl.proto").read()).group(1)


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


def protocols(unit, ta, dead=False):
    """The protocols the database runs for one polled unit: (period s, seconds on the line)."""
    u = "#%d " % unit
    return [
        (0.1, tx(u + "MN1", "MONI1=FFFH", ta, dead)),
        (0.1, tx(u + "MN2", "MONI2=FFFH", ta, dead)),
        (1.0, tx(u + "REN", None, ta) + tx(u + "STS", "#%d CO RM" % unit, ta, dead)),
        (5.0, tx(u + "CH0?", "CH0=FFFFH", ta, dead)),
        (5.0, tx(u + "SW?", "SW1", ta, dead) + tx(u + "CH1?", "CH1=FFFFH", ta, dead)),
    ]


def bus_rate(units, ta, dead=()):
    """Bus arithmetic: the monitors run at 10 Hz (SCAN_MON) unless the line is full; then the
    supplies share evenly what the status and echo polls leave."""
    fixed = sum(t / p for u in units for p, t in protocols(u, ta, u in dead) if p > 0.1)
    mon = sum(t for u in units for p, t in protocols(u, ta, u in dead) if p == 0.1)
    return min(10.0, (1.0 - fixed) / mon)


# --- measurement ---------------------------------------------------------------------------------

READS = (("MN1", "voltage:read"), ("MN2", "current:read"), ("CH0?", "voltage:get"),
         ("CH1?", "current:get"))


def measure(units_by_chain, seconds=20.0):
    """Update rates per (unit, command) seen by a Channel Access client (MDEL -1 for the
    measurement, so that every processing is posted). SW? is read with CH1? (forward link), and
    STS is what the simulator's reply count leaves: replies - MN1 - MN2 - CH0? - SW? - CH1?, and
    with the status check (T22) once more CH0?, SW? and CH1? (each has an STS before it)."""
    pvs = {(u, n): "AU-20P7-%d:%s" % (u, s) for us in units_by_chain.values() for u in us
           for n, s in READS}
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
    rate = {k: n / seconds for k, n in counts.items()}
    for m in monitors:
        m.clear_callbacks()
        m.disconnect()
    for pv in pvs.values():
        put(pv + ".MDEL", 0)
    for c in ctls.values():
        c.close()
    for ch, units in units_by_chain.items():
        s = stats[ch]
        for u in units:
            replies = s["per_unit"].get(str(u), {}).get("replies", 0) / s["elapsed_s"]
            rate[u, "SW?"] = rate[u, "CH1?"]
            rate[u, "STS"] = replies - sum(rate[u, n] for n in ("MN1", "MN2", "CH0?", "SW?", "CH1?"))
            if STATUS_CHECK:                 # the status checks of CH0?, SW?, CH1? are not polls
                rate[u, "STS"] -= sum(rate[u, n] for n in ("CH0?", "SW?", "CH1?"))
    return rate


def set_turnaround(ms):
    for ch in CHAINS:
        with control(ch) as c:
            if ms is None:
                c.release("line.turnaround_ms")
            else:
                c.set("line.turnaround_ms", ms)


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
    for d in ("AU-20P7-3", "AU-20P7-4"):            # both supplies of the chain on, polled
        if get(d + ":SetToggleOutput") == 0:
            put(d + ":SetToggleOutput", 1)
    high = latency_of_sets(pv, 3)
    put(pv + ".PRIO", "LOW")
    try:
        low = latency_of_sets(pv, 3)
    finally:
        put(pv + ".PRIO", "HIGH")
    lines = ["PRIO of AU-20P7-3:voltage:setpoint, caput -> CH0 at the simulator, chain mat_co "
             "polled (units 3 and 4), %d sets each:" % len(high)]
    for name, v in (("HIGH", high), ("LOW ", low)):
        lines.append("  %s  median %5.1f ms   max %5.1f ms" % (
            name, statistics.median(v) * 1000, max(v) * 1000))
    report("\n".join(lines), capsys)
    assert statistics.median(high) < 0.025
    assert statistics.median(high) < statistics.median(low) / 2


def test_rate_report(capsys):
    """Two chains with two supplies each. Requirement: every polled monitor PV of a chain updates
    at the same rate, within 10 % of the bus arithmetic, capped at SCAN_MON (10 Hz)."""
    for d in ("AU-20P7-1", "AU-20P7-2", "AU-20P7-3", "AU-20P7-4"):
        if get(d + ":SetToggleOutput") == 0:
            put(d + ":SetToggleOutput", 1)
    with control("mat_co") as c:
        ta = c.info()["settings"]["turnaround_ms"]
    rows = []
    cases = [("turnaround %g ms (configuration)" % ta, ta), ("turnaround 16 ms", 16.0)]
    try:
        for label, t in cases:
            set_turnaround(None if t == ta else t)
            chains = CHAINS
            time.sleep(1.0)
            rate = measure(chains)
            for ch, units in chains.items():
                bus = bus_rate(units, t)
                for u in units:
                    rows.append(dict(case=label, chain=ch, unit=u, bus=bus,
                                     **{n: rate[u, n] for n in ("MN1", "MN2", "STS", "CH0?", "SW?")}))
    finally:
        set_turnaround(None)
    lines = ["Update rates, Hz. bus = bus arithmetic (monitors at 10 Hz unless the line is full,",
             "then shared evenly). V, I = voltage:read, current:read as a Channel Access client sees",
             "them; STS, CH0?, SW? = the status and echo polls (wanted: 1, 0.2, 0.2).",
             "%-32s %-7s %4s | %5s | %5s %5s %5s | %5s %5s %5s" % (
                 "case", "chain", "unit", "bus", "V", "I", "V/bus", "STS", "CH0?", "SW?")]
    for r in rows:
        lines.append("%-32s %-7s %4d | %5.2f | %5.2f %5.2f %4.0f%% | %5.2f %5.2f %5.2f" % (
            r["case"], r["chain"], r["unit"], r["bus"], r["MN1"], r["MN2"],
            100 * r["MN1"] / r["bus"], r["STS"], r["CH0?"], r["SW?"]))
    report("\n".join(lines), capsys)
    for r in rows:
        for n in ("MN1", "MN2"):
            assert r[n] == pytest.approx(r["bus"], rel=0.1), (n, r)    # even, as the arithmetic
            assert r[n] <= 10.0 * 1.02, (n, r)                         # never above SCAN_MON
        assert r["STS"] == pytest.approx(1.0, abs=0.15), r              # not starved
        assert r["CH0?"] == pytest.approx(0.2, abs=0.11), r
        assert r["SW?"] == pytest.approx(0.2, abs=0.11), r


def test_rate_with_a_silent_neighbour(capsys):
    put("AU-20P7-3:SetToggleOutput", 1)
    with control("mat_co") as c:
        c.fault("silent", unit=4)
        try:
            time.sleep(1.5)
            rate = measure({"mat_co": [3]})
        finally:
            c.clear("silent")
    bus = bus_rate([3, 4], 5.0, dead=(4,))
    report("Unit 4 silent (reply timeout and wait %d ms): unit 3 keeps %.2f (voltage:read) and %.2f "
           "(current:read) updates/s; bus arithmetic with the timeouts %.2f"
           % (REPLY_TIMEOUT * 1000, rate[3, "MN1"], rate[3, "MN2"], bus), capsys)
    for n in ("MN1", "MN2"):
        assert rate[3, n] == pytest.approx(bus, rel=0.1)
    wait_for(lambda: get("AU-20P7-4:voltage:read.SEVR") == 0, 5, "unit 4 back")


# Lines of the IOC log that mean an error (as in devtest/example). StreamDevice's messages about
# the traffic (no reply, mismatch, disconnected) are not database, protocol or link errors: the
# faults of this case cause them on purpose, and the functional tests check their effect. They
# are counted per port in the report.
ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad |mismatch|does not match|too short|no match|disconnected"
                   r"|no reply|timeout|not connected", re.I)
# (Two threads of the IOC can print at the same moment: a line may start with two time stamps.)
TRAFFIC = re.compile(r"^(?:\d{4}/\d\d/\d\d \S+ )*(?P<port>\S+) (\S+:? )?(No reply within \d+ ms|\d+ additional errors|"
                     r"device \S+ 0 disconnected|lockRequest: |Input \"[^\"]*\"|mismatch after|"
                     r"got \"|No match for |Input \"[0-9A-F]+H\" does not match format \"%=04X\")"
                     r"|^(?P<ca>dbCaTask) ca_array_put Channel write request failed"
                     r"|^\S+ has DB CA link to \S+$"
                     # autosave at the first IOC start: no saved file yet (the defaults apply)
                     r"|^save_restore: (Can't open file '/tmp/limits\.sav|Trying backup file|"
                     r"Can't figure out which seq file|so I'm just going to start with|"
                     r"Can't find a file to restore from|\*+$|Can't open save file)"
                     r"|^save_restore:write_save_file: Backup file \(/tmp/limits\.savB\) bad or "
                     r"not found"
                     r"|^devtest: IOC restarted on request")


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
            key = m.group("port") or m.group("ca") or "autosave and harness"
            ports[key] = ports.get(key, 0) + 1
    report("IOC log: no database, protocol or link error; StreamDevice traffic messages per "
           "port (from the faults): %s" % (ports or "none"), capsys)


def report(text, capsys):
    with open(os.path.join(BUILD, "rate_report.txt"), "a") as f:
        f.write(text + "\n\n")
    with capsys.disabled():
        print("\n" + text)
