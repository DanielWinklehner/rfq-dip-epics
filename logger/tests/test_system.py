"""The logger against the running emulation (make -C logger test, run.sh). The tests run in the
order of this file; some use what an earlier one recorded (WINDOWS).

Every time limit is stated where it is used, with where it comes from. The logger's own
periods: one tick per second (TICK), an interval of tiers 2 and 3 is closed 2 s after its end
(CLOSE_DELAY), the state records are written once a second, LOGGER:alive:get alarms after 5 s
without a count and is scanned once a second.
"""
import datetime
import json
import math
import os
import subprocess
import threading
import time
import urllib.request

import epics
import psycopg
import pytest

import system as S
from system import reg
from mist2log import core, store

TICK, CLOSE_DELAY = 1.0, 2.0
WRITTEN = TICK + 2.0       # a row is in the database one tick after it arrived, plus the write
UTC = datetime.timezone.utc
STATUS = "LOGGER"
BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build")
WINDOWS = {}               # what one test leaves to a later one

DSN = {"host": "127.0.0.1", "port": int(os.environ["MIST2LOG_DB_PORT"]), "dbname": "mist2log",
       "user": "mist2log", "password": os.environ["MIST2LOG_DB_PASSWORD"]}
LOGGED = {n: s for n, s in reg.pvs.items() if s.get("log", "none") != "none"}


def q(sql, args=(), dbname="mist2log"):
    with psycopg.connect(**dict(DSN, dbname=dbname), autocommit=True) as conn:
        return conn.execute(sql, args).fetchall()


def pv_id(name):
    return q("SELECT id FROM pv WHERE name = %s", (name,))[0][0]


def ts(t):
    return datetime.datetime.fromtimestamp(t, UTC)


def request(line, timeout=120.0):
    """A request to run.sh (the container has no Docker): 'stop db', 'start logger', 'buffer 2000'..."""
    folder = os.path.join(BUILD, "requests")
    name = os.path.join(folder, "%d-%d" % (os.getpid(), time.monotonic_ns()))
    with open(name + ".new", "w") as handle:
        handle.write(line + "\n")
    os.rename(name + ".new", name + ".req")
    S.wait_for(lambda: os.path.exists(name + ".done"), timeout, "run.sh executes %r" % line, interval=0.2)
    status, _, out = open(name + ".done").read().partition(" ")
    os.remove(name + ".done")
    assert status == "0", "%s: %s" % (line, out)
    return out


def status(key):
    return S.get("%s:%s:get" % (STATUS, key))


class Counter:
    """A second Channel Access client: every monitor update of a PV, with its time stamp."""

    def __init__(self, name):
        self.stamps, self.lock = [], threading.Lock()
        self.pv = epics.PV(name, form="time", auto_monitor=True, callback=self._cb)
        assert self.pv.wait_for_connection(5), name

    def _cb(self, timestamp=None, **kw):
        with self.lock:
            self.stamps.append(timestamp)

    def between(self, t0, t1):
        with self.lock:
            return [t for t in self.stamps if t0 <= t < t1]

    def close(self):
        self.pv.clear_callbacks()
        self.pv.disconnect()


def raw_stamps(name, t0, t1):
    return [r[0].timestamp() for r in q("SELECT t FROM raw WHERE pv = %s AND t >= %s AND t < %s AND severity IS NOT NULL "
                                        "ORDER BY t", (pv_id(name), ts(t0), ts(t1)))]


FAST = reg.role("fil_heat", "iread")     # the TDK's current read-back, polled at 10 Hz (tdk.db)


# --- the PV list -----------------------------------------------------------------------------------
def test_every_pv_of_the_list_is_subscribed():
    # Limit 30 s: the logger connects at its start (run.sh waits for it); CA connects in well
    # under a second, the state records are written once a second.
    S.wait_for(lambda: status("alive") == 1, 30, "LOGGER:alive:get is 1")
    S.wait_for(lambda: status("connected") == len(LOGGED) and status("disconnected") == 0, 30,
               lambda: "LOGGER:connected:get %s of %d, disconnected %s" % (status("connected"), len(LOGGED), status("disconnected")))
    rows = dict(q("SELECT name, connected FROM pv WHERE tier <> 'none'"))
    assert set(LOGGED) <= set(rows), sorted(set(LOGGED) - set(rows))
    assert [n for n in LOGGED if not rows[n]] == []
    assert {n: s["log"] for n, s in LOGGED.items()} == dict(q("SELECT name, tier FROM pv WHERE name = ANY(%s)", (list(LOGGED),)))
    # the logger does not log its own state records (R8)
    assert not any(n.startswith(STATUS + ":") for n in LOGGED)


def test_a_set_point_written_appears_as_a_change_and_as_an_event_with_old_and_new():
    name = reg.role("mfc", "sp_cmd")
    low, high = reg.pvs[name]["test"]
    old = S.get(name)
    new = old + 5 if old + 5 <= high else old - 5
    t0 = time.time()
    S.put(name, new)
    try:
        # Limit WRITTEN: one tick and the write
        S.wait_for(lambda: q("SELECT value FROM changes WHERE pv = %s AND t >= %s AND value = %s",
                             (pv_id(name), ts(t0 - 0.5), new)), WRITTEN + 2, "the change of %s in the database" % name)
        events = q("SELECT old, new FROM events WHERE pv = %s AND kind = 'set' AND t >= %s ORDER BY t", (pv_id(name), ts(t0 - 0.5)))
        assert (old, new) in [(float(o), float(n)) for o, n in events], events
    finally:
        S.put(name, old)


# --- R2: raw, R3: intervals ------------------------------------------------------------------------
def test_raw_rows_of_a_10_hz_pv_equal_the_monitor_updates_of_a_second_client():
    counter = Counter(FAST)
    t0 = math.ceil(time.time()) + 2
    t1 = t0 + 60
    time.sleep(max(0.0, t1 + CLOSE_DELAY + WRITTEN - time.time()))
    counted = counter.between(t0, t1)
    counter.close()
    stored = raw_stamps(FAST, t0, t1)
    WINDOWS["fast"] = (t0, t1)
    # polled at 10 Hz; a monitor posts only a change, so somewhat fewer: more than 5 per second
    assert len(counted) >= 5 * 60, "%s is not a fast PV: %d updates in a minute" % (FAST, len(counted))
    assert len(stored) == len(counted)
    assert max(abs(a - b) for a, b in zip(stored, counted)) < 2e-6     # timestamptz keeps microseconds


def expected_intervals(rows, start, width, count):
    """Mean, min, max and the valid share per interval from the raw rows (t, value, severity),
    independently of the logger: each value holds until the next row, weighted by time; a row
    INVALID or without severity holds no valid value; rows before `start` give the state at it."""
    out = []
    for k in range(count):
        a, b = start + k * width, start + (k + 1) * width
        segs = []
        for i, (t, v, sev) in enumerate(rows):
            end = rows[i + 1][0] if i + 1 < len(rows) else math.inf
            lo, hi = max(t, a), min(end, b)
            if hi > lo and sev is not None and sev < 3:
                segs.append((hi - lo, v))
        total = sum(d for d, _ in segs)
        out.append((a, sum(d * v for d, v in segs) / total if total else None, min((v for _, v in segs), default=None),
                    max((v for _, v in segs), default=None), total / width))
    return out


def test_seconds_and_minutes_of_a_changing_pv_against_the_raw_rows():
    t0, t1 = WINDOWS["fast"]
    rows = [(r[0].timestamp(), r[1], r[2]) for r in q(
        "SELECT t, value, severity FROM raw WHERE pv = %s AND t >= %s AND t < %s ORDER BY t", (pv_id(FAST), ts(t0 - 5), ts(t1)))]
    for table, width in (("seconds", 1), ("minutes", 60)):
        start = math.ceil(t0 / width) * width
        count = int((t1 - start) // width)
        if count == 0:
            continue
        want = expected_intervals(rows, start, width, count)
        # every interval as the reader gets it: its own row, or (no update in it) the value held
        got = q("SELECT t, value, min, max, valid FROM log_read(%s, %s, %s, %s)",
                (FAST, ts(start), ts(start + count * width), table))
        assert len(got) == count, (table, len(got), count)
        stored = q("SELECT count(*) FROM %s WHERE pv = %%s AND t >= %%s AND t < %%s" % table, (pv_id(FAST), ts(start), ts(start + count * width)))
        assert stored[0][0] >= count / 2, (table, stored)           # most intervals hold a change
        for (a, mean, mn, mx, share), (t, gmean, gmn, gmx, valid) in zip(want, got):
            assert t.timestamp() == a and valid == pytest.approx(share, abs=1e-6), (table, a, valid, share)
            assert (gmean, gmn, gmx) == ((pytest.approx(mean, rel=1e-9) if mean is not None else None), mn, mx), (table, a)


def test_a_constant_pv_reads_as_its_value_in_every_second_and_minute():
    # A raw PV whose last row is valid and old enough for a whole closed minute after it: it holds
    # (spare channels, and readings without noise). Limit 180 s: the logger may have started just
    # before the suite, its first rows are its start.
    def held(age):
        return q("SELECT p.name, r.value, r.t FROM pv p CROSS JOIN LATERAL (SELECT * FROM raw x WHERE x.pv = p.id "
                 "ORDER BY x.t DESC LIMIT 1) r WHERE p.tier = 'raw' AND p.kind = 'number' AND r.severity < 3 "
                 "AND r.t < %s ORDER BY p.name", (ts(time.time() - age),))
    S.wait_for(lambda: held(125), 180, "a raw PV that holds its value for 125 s")
    name, value, since = held(125)[0]
    since = since.timestamp()
    end = math.floor(time.time() - CLOSE_DELAY - 1)
    start = max(math.ceil(since) + 1, end - 100)
    secs = q("SELECT t, value, min, max, valid, kind FROM log_read(%s, %s, %s, 'seconds')", (name, ts(start), ts(end)))
    assert len(secs) == end - start and {r[5] for r in secs} == {"held"}
    assert all((r[1], r[2], r[3], r[4]) == (value, value, value, 1.0) for r in secs), (name, secs[:3])
    stored = q("SELECT count(*) FROM seconds WHERE pv = %s AND t >= %s", (pv_id(name), ts(start)))[0][0]
    assert stored == 0                     # stored once, at its change: held values are not rows
    m0, m1 = math.ceil(since / 60) * 60, math.floor(end / 60) * 60
    assert m1 > m0
    mins = q("SELECT value, kind FROM log_read(%s, %s, %s, 'minutes')", (name, ts(m0), ts(m1)))
    assert mins == [(value, "held")] * ((m1 - m0) // 60), (name, mins)


# --- faults ------------------------------------------------------------------------------------------
def test_a_silent_simulator_gives_alarm_events_and_a_gap_not_a_held_value():
    device = "thermo_hv"
    sim = reg.devices[device]["simulators"][0]
    names = [n for n in reg.fails_with(sim) if LOGGED.get(n, {}).get("log") == "raw"]
    assert names
    with S.fault(sim, "silent"):
        t_fault = time.time()
        # Limit 5 s: fault to INVALID (emulation/tests/README.md, default)
        S.wait_for(lambda: S.all_invalid(names), 5, lambda: S.bad(names, lambda s: s == S.INVALID))
        t_invalid = time.time()
        time.sleep(6)
        t_end = time.time()
    # Limit 20 s: recovery after clear (emulation/tests/README.md)
    S.wait_for(lambda: S.not_invalid(names), 20, lambda: S.bad(names, lambda s: s != S.INVALID))
    time.sleep(CLOSE_DELAY + WRITTEN + 1)
    WINDOWS["gap"] = (names[0], t_invalid + 1, t_end - 1)
    for name in names:
        alarms = q("SELECT new FROM events WHERE pv = %s AND kind = 'alarm' AND t >= %s ORDER BY t", (pv_id(name), ts(t_fault - 1)))
        assert [a[0] for a in alarms][:1] == ["INVALID"] and alarms[-1][0] == "NO_ALARM", (name, alarms)
        secs = q("SELECT kind, value FROM log_read(%s, %s, %s, 'seconds')",
                 (name, ts(math.ceil(t_invalid + 1)), ts(math.floor(t_end - 1))))
        assert secs and all(r == ("gap", None) for r in secs), (name, secs)
        raws = q("SELECT kind FROM log_read(%s, %s, %s, 'raw')", (name, ts(t_invalid + 1), ts(t_end - 1)))
        assert {r[0] for r in raws} == {"gap"}, (name, raws)


def test_reading_tool_returns_the_numbers_of_a_direct_query_and_marks_gaps(tmp_path):
    t0, t1 = WINDOWS["fast"]
    env = dict(os.environ, MIST2LOG_READ_PASSWORD=os.environ["MIST2LOG_READER_PASSWORD"])

    def tool(*args):
        out = tmp_path / "out.csv"
        subprocess.run(["python", "-m", "mist2log.read", *args, "-o", str(out)], check=True, env=env)
        import csv
        return list(csv.DictReader(open(out)))

    rows = tool(FAST, "--from", ts(t0).isoformat(), "--to", ts(t1).isoformat(), "--tier", "raw")
    direct = q("SELECT t, value FROM raw WHERE pv = %s AND t >= %s AND t < %s AND severity < 3 ORDER BY t",
               (pv_id(FAST), ts(t0), ts(t1)))
    values = [(datetime.datetime.fromisoformat(r["t"]), float(r["value"])) for r in rows if r["kind"] == "value"]
    assert values == [(t, v) for t, v in direct]
    assert rows[0]["kind"] == "held" and rows[-1]["kind"] == "held"      # the value at both ends
    rows = [r for r in tool(FAST, "--from", ts(math.ceil(t0)).isoformat(), "--to", ts(math.floor(t1)).isoformat(),
                            "--tier", "seconds") if r["kind"] == "value"]
    direct = q("SELECT t, mean, min, max FROM seconds WHERE pv = %s AND t >= %s AND t < %s ORDER BY t",
               (pv_id(FAST), ts(math.ceil(t0)), ts(math.floor(t1))))
    assert [(datetime.datetime.fromisoformat(r["t"]), float(r["value"]), float(r["min"]), float(r["max"])) for r in rows] == direct
    name, a, b = WINDOWS["gap"]
    rows = tool(name, "--from", ts(a).isoformat(), "--to", ts(b).isoformat())
    assert rows and {r["kind"] for r in rows} == {"gap"} and {r["value"] for r in rows} == {""}


# --- a loop in PID (F1, F2) ------------------------------------------------------------------------
LOOP = next(d for d, dev in reg.devices.items() if dev.get("drives"))


def door():
    """The interlock simulator and the signal of its first door switch (as test_06, test_09)."""
    ilk = next(d for d, dev in reg.devices.items() if dev["class"] == "interlock")
    return reg.devices[ilk]["simulators"][0], sorted(reg.devices[ilk]["channels"])[0]


def test_a_loop_in_pid_writes_a_signal_not_set_commands_and_its_mode_event_has_its_reason():
    lp = reg.devices[LOOP]
    roles, macros = lp["roles"], lp["loads"][0]["macros"]
    act = lp["drives"][0]["pv"]
    conds = [(macros["C%d" % n], float(macros["R%d" % n])) for n in (1, 2, 3)]
    outs = [reg.role(reg.pvs[c]["device"], "out_cmd") for c, _ in conds if reg.devices[reg.pvs[c]["device"]]["class"] == "supply"]
    before = {pv: S.get(pv) for pv in outs + [act]}
    sim, signal = door()
    # Limit 30 s: the service alive (its counter), the supplies' first contact (GRACE)
    S.wait_for(lambda: S.get(roles["service"]) == 1, 30, "the loop service alive")
    try:
        for pv in outs:
            S.put(pv, 1)
        # Limit 10 s: output states polled every 1 s, the permit records every period
        S.wait_for(lambda: all(S.get(c) == r for c, r in conds), 10, lambda: S.describe([c for c, _ in conds]))
        S.put(act, S.get(roles["outmin"]) + 1.0)       # inside the output limits: the output ramps
        time.sleep(1.5)                                 # the service sees the heartbeat change once
        counter = Counter(act)
        S.put(roles["mode_cmd"], 1)
        # Limit 1 s: the service decides in its next cycle (0.2 s), LOOP.md
        S.wait_for(lambda: S.get(roles["mode"]) == 1, 1.0, lambda: S.describe([roles["mode"], roles["reason"]]))
        t_pid = time.time()
        time.sleep(4)
        t_back0 = time.time()
        S.sim_set(sim, signal, 0)                       # a door open: hand-back "interlock open"
        # Limit 1 s: interlock box polled every 0.1 s, then one cycle (LOOP.md, section 4)
        S.wait_for(lambda: S.get(roles["mode"]) == 0, 1.0, "hand-back")
        t_back = time.time()
        words = S.get(roles["reason"], as_string=True)
    finally:
        if (sim, signal) in S.forced:
            S.sim_release(sim, signal)
        S.put(roles["mode_cmd"], 0)
        for pv, value in before.items():
            S.put(pv, value)
    writes = counter.between(t_pid + 0.3, t_back0)
    counter.close()
    time.sleep(WRITTEN + core.CONTEXT_WAIT + CLOSE_DELAY)
    assert len(writes) >= 10, "the loop wrote %d times in PID" % len(writes)
    a = pv_id(act)
    sets = q("SELECT t FROM events WHERE pv = %s AND kind = 'set' AND t > %s AND t < %s", (a, ts(t_pid + 0.3), ts(t_back0)))
    changes = q("SELECT t FROM changes WHERE pv = %s AND t > %s AND t < %s", (a, ts(t_pid + 0.3), ts(t_back0)))
    assert (sets, changes) == ([], []), "the loop's writes became set commands"
    raw = raw_stamps(act, t_pid + 0.3, t_back0)
    assert len(raw) == len(writes) and max(abs(x - y) for x, y in zip(raw, writes)) < 2e-6     # every write, as a signal
    assert q("SELECT count(*) FROM seconds WHERE pv = %s AND t >= %s AND t < %s", (a, ts(math.ceil(t_pid)), ts(math.floor(t_back0))))[0][0] \
        == math.floor(t_back0) - math.ceil(t_pid)
    # outside PID a write is a set command again: the restore above
    assert q("SELECT count(*) FROM events WHERE pv = %s AND kind = 'set' AND t > %s", (a, ts(t_back)))[0][0] >= 1
    # the reader gets the whole series of the actuator: before, in and after PID
    kinds = {r[0] for r in q("SELECT kind FROM log_read(%s, %s, %s)", (act, ts(t_pid - 2), ts(t_back + 1)))}
    assert "gap" not in kinds, kinds
    mode = q("SELECT old, new, detail FROM events WHERE pv = %s AND t >= %s ORDER BY t", (pv_id(roles["mode"]), ts(t_back0 - 0.5)))
    assert mode and mode[0][:2] == ("PID (1)", "MANUAL (0)"), mode
    assert mode[0][2] == "%s: %s (%d)" % (roles["reason"], words, reg.pvs[roles["reason"]]["states"].index(words)), mode


def test_an_ioc_stopped_and_started_gives_disconnect_and_return():
    names = [n for n, s in LOGGED.items() if s["ioc"] == "ioc_hv"]
    t0 = time.time()
    request("stop ioc-hv")
    # Limit 5 s: the IOC's connections close with its container (at once), one tick and the write
    S.wait_for(lambda: q("SELECT count(DISTINCT pv) FROM events WHERE kind = 'connection' AND new = 'lost' AND t >= %s",
                         (ts(t0),))[0][0] >= len(names), 5 + WRITTEN, "a disconnect event for each of %d PVs" % len(names))
    gaps = q("SELECT count(*) FROM raw r JOIN pv p ON p.id = r.pv WHERE r.t >= %s AND r.severity IS NULL AND r.flags = 0",
             (ts(t0),))[0][0]
    assert gaps == sum(1 for n in names if LOGGED[n]["log"] == "raw")
    t1 = time.time()
    request("start ioc-hv")
    # Limit 60 s: the container's start (healthy within 30 s, as in the emulation's tests), then
    # Channel Access finds the IOC again: its search repeats within seconds after a beacon
    S.wait_for(lambda: q("SELECT count(DISTINCT pv) FROM events WHERE kind = 'connection' AND new = 'back' AND t >= %s",
                         (ts(t1),))[0][0] >= len(names), 60, "a return event for each of %d PVs" % len(names))
    S.wait_for(lambda: status("disconnected") == 0, 10, "LOGGER:disconnected:get 0")


def test_never_processed_records_are_not_stored_in_1990():
    old = q("SELECT 'raw', count(*) FROM raw WHERE t < '2000-01-01' UNION ALL SELECT 'changes', count(*) FROM changes "
            "WHERE t < '2000-01-01' UNION ALL SELECT 'events', count(*) FROM events WHERE t < '2000-01-01'")
    assert all(n == 0 for _, n in old), old
    udf = [n for n in LOGGED if S.read(n)["timestamp"] < core.NEVER_PROCESSED_BEFORE]
    assert udf, "no record of the emulation is unprocessed after the IOC start"
    time.sleep(WRITTEN)
    latest = {}
    for name in udf:
        rows = q("SELECT t, flags FROM changes WHERE pv = %s AND severity IS NOT NULL UNION ALL "
                 "SELECT t, flags FROM raw WHERE pv = %s AND severity IS NOT NULL ORDER BY 1 DESC LIMIT 1", (pv_id(name),) * 2)
        latest[name] = rows[0] if rows else None
    # a record processed meanwhile (the loop service writes its request at its first contact)
    # has a real time stamp now and a row of its own; every one still unprocessed (of both IOCs:
    # the rack IOC was not restarted) has its last row under the logger's time, flagged
    still = [n for n in udf if S.read(n)["timestamp"] < core.NEVER_PROCESSED_BEFORE]
    assert still
    for name in still:
        row = latest[name]
        assert row and row[1] & core.FLAG_UDF_TIME and row[0].timestamp() > core.NEVER_PROCESSED_BEFORE, (name, row)


# --- the logger's own state -----------------------------------------------------------------------
def test_status_records_count_and_alive_alarms_when_the_logger_stops():
    a = status("count")
    time.sleep(3.2)
    assert status("count") - a >= 2              # once a second
    assert status("rows") > 0 and S.get("%s:db:get" % STATUS, as_string=True) == "connected"
    request("stop logger")
    t0 = time.time()
    # Limit 7 s: TIMEOUT 5 s without a count, alive:get scanned once a second, the last count
    # up to a second before the stop
    S.wait_for(lambda: status("alive") == 0 and S.sevr("%s:alive:get" % STATUS) == S.MAJOR, 7,
               "LOGGER:alive:get 0 MAJOR")
    took = time.time() - t0
    assert took >= 3.5, "alive:get alarmed %.1f s after the stop, before TIMEOUT" % took
    request("start logger")
    # Limit 30 s: the logger's start (registry, database, Channel Access connections)
    S.wait_for(lambda: status("alive") == 1, 30, "LOGGER:alive:get 1 after the start")
    S.wait_for(lambda: status("disconnected") == 0 and status("connected") == len(LOGGED), 30, "every PV connected again")
    starts = q("SELECT new FROM events WHERE kind = 'logger' AND new IN ('start', 'stop') AND t >= %s ORDER BY t", (ts(t0 - 5),))
    assert [n for n, in starts] == ["stop", "start"], starts
    # the time it did not run is a gap of every PV, written by the logger
    assert q("SELECT count(DISTINCT pv) FROM raw WHERE flags = %s AND t >= %s", (core.FLAG_LOGGER, ts(t0 - 5)))[0][0] == \
        sum(1 for s in LOGGED.values() if s["log"] == "raw")


# --- R6: the database lost ------------------------------------------------------------------------
def outage(seconds, limit):
    """The database stopped for `seconds`, then started; returns when the buffer holds no more
    than the batch of one tick (at most 400 rows: about three times the rows of a second)."""
    counter = Counter(FAST)
    time.sleep(2)
    t0 = time.time()
    request("stop db")
    # Limit 8 s: the next write fails (one tick), the connection timeout is 5 s
    S.wait_for(lambda: S.get("%s:db:get" % STATUS, as_string=True) == "lost", 8, "LOGGER:db:get lost")
    time.sleep(max(0.0, t0 + seconds - time.time()))
    fill = status("buffer")
    WINDOWS.setdefault("stats_outage", (fill, request("stats")))
    request("start db")
    # Limit 60 s: the database's start (healthy) and the logger's next attempt (every second)
    S.wait_for(lambda: S.get("%s:db:get" % STATUS, as_string=True) == "connected" and status("buffer") <= 100.0 * 400 / limit,
               60, lambda: "LOGGER:db:get connected and the buffer empty (buffer %s %%)" % status("buffer"))
    t1 = time.time()
    time.sleep(WRITTEN + 1)
    counter.close()
    return counter, t0, t1, fill


def test_database_stopped_for_a_minute_nothing_lost_order_kept():
    counter, t0, t1, fill = outage(60, int(os.environ["MIST2LOG_BUFFER_ROWS"]))
    counted = counter.between(t0 - 1, t1)
    stored = raw_stamps(FAST, t0 - 1, t1)
    assert fill > 0
    assert len(stored) == len(counted) and max(abs(a - b) for a, b in zip(stored, counted)) < 2e-6
    kinds = [r[0] for r in q("SELECT new FROM events WHERE kind = 'logger' AND t >= %s ORDER BY t", (ts(t0 - 1),))]
    assert kinds == ["database lost", "database back"], kinds
    assert status("dropped") == 0
    WINDOWS["buffer"] = (fill, 60)


def test_database_stopped_longer_than_the_buffer_the_loss_is_counted_and_logged():
    request("buffer 3000")        # rows: about 20 s of the full emulation (139.6 rows per second at rest, LOGGER.md section 10)
    S.wait_for(lambda: status("alive") == 1 and status("connected") == len(LOGGED), 30, "the logger with the small buffer")
    try:
        counter, t0, t1, fill = outage(45, 3000)
        assert status("dropped") > 0 and S.sevr("%s:dropped:get" % STATUS) == S.MINOR
        lost = q("SELECT value, t FROM events WHERE kind = 'logger' AND new = 'rows lost' AND t >= %s", (ts(t0 - 1),))
        assert len(lost) == 1 and lost[0][0] == status("dropped"), lost
        rows = q("SELECT t, flags, severity FROM raw WHERE pv = %s AND t >= %s AND t < %s ORDER BY t", (pv_id(FAST), ts(t0 - 1), ts(t1)))
        gap = [r for r in rows if r[1] == core.FLAG_LOGGER]
        resumed = [r for r in rows if r[1] == core.FLAG_RESUMED]
        assert len(gap) == 1 and len(resumed) == 1 and gap[0][0] < resumed[0][0], rows[-5:]
        # nothing is held across the loss: the reader shows a gap from the end of what was written
        reads = q("SELECT kind FROM log_read(%s, %s, %s, 'raw')", (FAST, gap[0][0], resumed[0][0]))
        assert {r[0] for r in reads} == {"gap"}, reads
    finally:
        request("buffer default")
        S.wait_for(lambda: status("alive") == 1 and status("connected") == len(LOGGED), 30, "the logger with its buffer")


# --- R5: life times --------------------------------------------------------------------------------
def test_life_times_with_shortened_values_drop_each_tier_on_its_own():
    jobs = dict(q("SELECT hypertable_name, config->>'drop_after' FROM timescaledb_information.jobs "
                  "WHERE proc_name = 'policy_retention'"))
    assert jobs == {"raw": "30 days", "seconds": "730 days"}, jobs          # the plan's life times
    with psycopg.connect(**DSN, autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS mist2log_lifetimes")
        conn.execute("CREATE DATABASE mist2log_lifetimes")
    try:
        short = {"raw": {"interval": None, "keep_days": 1 / 24}, "seconds": {"interval": 1, "keep_days": 2 / 24},
                 "minutes": {"interval": 60, "keep_days": None}, "events": {"interval": None, "keep_days": None}}
        with store.connect(dict(DSN, dbname="mist2log_lifetimes")) as conn:
            store.apply_schema(conn, short, chunks={t: "10 minutes" for t in store.CHUNKS})
            now = time.time()
            ages = [3 * 3600, 90 * 60, 10 * 60]
            for age in ages:
                t = ts(now - age)
                for table in ("raw", "changes"):
                    conn.execute("INSERT INTO %s (pv, t, value, severity, status) VALUES (1, %%s, 1, 0, 0)" % table, (t,))
                for table in ("seconds", "minutes"):
                    conn.execute("INSERT INTO %s VALUES (1, %%s, 1, 1, 1, 1, 0, 1, 0)" % table, (t,))
                conn.execute("INSERT INTO events (t, kind) VALUES (%s, 'logger')", (t,))
            conn.commit()
            for job, in conn.execute("SELECT job_id FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention'").fetchall():
                conn.execute("CALL run_job(%s)", (job,))
            conn.commit()
            left = {table: sorted(round((now - r[0].timestamp()) / 60) for r in conn.execute("SELECT t FROM %s" % table))
                    for table in ("raw", "changes", "seconds", "minutes", "events")}
    finally:
        with psycopg.connect(**DSN, autocommit=True) as conn:
            conn.execute("DROP DATABASE mist2log_lifetimes")
    assert left == {"raw": [10], "seconds": [10, 90], "changes": [10, 90, 180], "minutes": [10, 90, 180],
                    "events": [10, 90, 180]}, left


# --- R10: Grafana ------------------------------------------------------------------------------------
def test_a_batch_the_database_refuses_is_given_up_counted_and_logged():
    with psycopg.connect(**DSN, autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS mist2log_refused")
        conn.execute("CREATE DATABASE mist2log_refused")
    try:
        tiers = {"raw": {"interval": None, "keep_days": 30}, "seconds": {"interval": 1, "keep_days": 730},
                 "minutes": {"interval": 60, "keep_days": None}, "events": {"interval": None, "keep_days": None}}
        with store.connect(dict(DSN, dbname="mist2log_refused")) as conn:
            store.apply_schema(conn, tiers)

        class Settings:
            db = dict(DSN, dbname="mist2log_refused")
            reader_password = ""
            buffer_rows = 100000
        st = store.Store(Settings(), tiers)
        st.db_ok = True
        ch = core.Channel(1, "X", "raw", "number")
        rec = core.Recorder([ch])
        now = time.time()

        def batch(t, status):
            rec.update(ch, 1.0, None, 0, status, t, t)
            return rec.tick(t + 0.5)
        st.start()
        st.put(batch(now - 3, 0))
        st.put(batch(now - 2, 70000))                     # a status no smallint holds: the database refuses
        st.put(batch(now - 1, 0))
        # Limit 5 s: three batches, each one transaction
        S.wait_for(lambda: not st.queue, 5, "the writer goes on after the refused batch")
        refused = st.take_rejected()
        assert len(refused) == 1 and "out of range" in refused[0][3] and st.dropped == refused[0][2] > 0, refused
        from mist2log.service import loss_batch
        st.put(loss_batch(rec, refused[0][0], refused[0][1], refused[0][2], time.time(), "the database refused %d rows: %s"
                          % (refused[0][2], refused[0][3])), force=True)
        S.wait_for(lambda: not st.queue, 5, "the loss written")
        st.close()
        rows = q("SELECT t, severity, flags FROM raw ORDER BY t", dbname="mist2log_refused")
        events = q("SELECT new, value, detail FROM events WHERE kind = 'logger'", dbname="mist2log_refused")
    finally:
        with psycopg.connect(**DSN, autocommit=True) as conn:
            conn.execute("DROP DATABASE mist2log_refused")
    assert len([r for r in rows if r[2] == 0]) == 2              # both good batches written
    assert any(r[2] == core.FLAG_LOGGER for r in rows)           # a gap where the refused one was
    assert len(events) == 1 and events[0][0] == "rows lost" and "out of range" in events[0][2], events


def test_grafana_answers_and_has_one_dashboard_per_page_of_the_gui():
    base = "http://127.0.0.1:%s" % os.environ["MIST2LOG_GRAFANA_PORT"]
    health = json.load(urllib.request.urlopen(base + "/api/health", timeout=5))
    assert health["database"] == "ok"
    installed = [d for d, dev in reg.devices.items() if not dev["flags"].get("not_installed")]
    pages = ["Overview"] + list(dict.fromkeys(p for p in (reg.devices[d]["page"] for d in installed) if p)) + \
        ["Trends", "Infrastructure"]
    # Limit 40 s: Grafana rereads the dashboard files every 30 s
    def titles():
        found = json.load(urllib.request.urlopen(base + "/api/search?type=dash-db", timeout=5))
        return sorted(b["title"] for b in found)
    S.wait_for(lambda: titles() == sorted(pages), 40, lambda: "dashboards %s, pages %s" % (titles(), pages))
    # F3: a short window of a 10 Hz PV is drawn from raw, up to the newest seconds. The interval
    # is computed as Grafana's front end does: the range over the panel's points, not below the
    # data source's minimum interval.
    admin = urllib.request.Request(base + "/api/datasources/uid/mist2log")
    import base64
    admin.add_header("Authorization", "Basic " + base64.b64encode(("admin:" + os.environ["GRAFANA_ADMIN_PASSWORD"]).encode()).decode())
    minimum = json.load(urllib.request.urlopen(admin, timeout=5))["jsonData"].get("timeInterval", "1m")
    seconds = {"ms": 0.001, "s": 1, "m": 60}
    unit = minimum.lstrip("0123456789")
    minimum = float(minimum[:len(minimum) - len(unit)]) * seconds[unit]
    window = 120
    interval_ms = int(1000 * max(minimum, window / 1000.0))
    # the raw PV with the most rows in the last minute (the TDK's read-back is constant while its
    # output is off)
    def busiest():
        return q("SELECT p.name, count(*) FROM raw r JOIN pv p ON p.id = r.pv WHERE r.t > now() - interval '1 minute' "
                 "GROUP BY p.name ORDER BY count(*) DESC LIMIT 1")
    # Limit 90 s: a minute of data after the logger's start, from a PV updated at 5 Hz or more
    S.wait_for(lambda: busiest() and busiest()[0][1] >= 300, 90, lambda: "a busy raw PV: %s" % busiest())
    busiest = busiest()[0][0]
    sql = ("SELECT * FROM log_trend(ARRAY['%s'], $__timeFrom(), $__timeTo(), $__interval_ms) ORDER BY 1" % busiest)
    body = {"from": "now-%ds" % window, "to": "now", "queries": [{"refId": "A", "datasource": {"uid": "mist2log"},
            "rawSql": sql, "format": "time_series", "intervalMs": interval_ms, "maxDataPoints": 1000}]}
    asked = time.time()
    request_ = urllib.request.Request(base + "/api/ds/query", data=json.dumps(body).encode(),
                                      headers={"Content-Type": "application/json"})
    frame = json.load(urllib.request.urlopen(request_, timeout=10))["results"]["A"]["frames"][0]["data"]["values"]
    points = [(t / 1000.0, v) for t, v in zip(frame[0], frame[1]) if v is not None]
    stored = raw_stamps(busiest, asked - window + 5, asked - 5)
    inside = [t for t, _ in points if asked - window + 5 <= t < asked - 5]
    # raw: every row, at its own time (seconds or minutes would give one point per interval); the
    # only other points are the held value 1 ms before a gap (F7)
    assert len(stored) > 10
    ms = lambda t: math.floor(t * 1000 + 1e-6)          # Grafana keeps milliseconds
    drawn = {round(t * 1000) for t in inside}
    missing = [t for t in stored if ms(t) not in drawn]
    assert not missing, (len(missing), len(stored))
    gaps = {ms(r[0].timestamp() - 0.001) for r in q("SELECT t FROM raw WHERE pv = %s AND t >= %s AND (severity IS NULL "
                                                         "OR severity >= 3)", (pv_id(busiest), ts(asked - window)))}
    extra = drawn - {ms(t) for t in stored}
    assert extra <= gaps, sorted(extra - gaps)[:5]
    # the newest data is drawn, and the data is complete up to at most one tick and the write
    # before the query (limit 3 s)
    newest = q("SELECT max(t) FROM raw WHERE pv = %s AND t < %s", (pv_id(busiest), ts(asked)))[0][0].timestamp()
    through = q("SELECT raw_through FROM state")[0][0].timestamp()
    # (F7: the last point is that value held up to where the data ends, 1 ms before it)
    assert newest - 0.001 <= points[-1][0] and abs(points[-1][0] - (through - 0.001)) < 0.002 and through > asked - 3, \
        (points[-1][0], newest, through, asked)
    # F7: a PV that does not change within the window is drawn over the whole window, up to the
    # newest data: the loop's set point (an events PV). The window lies after the logger's start.
    def ask(sql, window):
        body = {"from": "now-%ds" % window, "to": "now", "queries": [{"refId": "A", "datasource": {"uid": "mist2log"},
                "rawSql": sql, "format": "time_series", "intervalMs": int(1000 * max(minimum, window / 1000.0)),
                "maxDataPoints": 1000}]}
        req = urllib.request.Request(base + "/api/ds/query", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        frames = json.load(urllib.request.urlopen(req, timeout=10))["results"]["A"]["frames"]
        out = {}
        for f in frames:                    # long or wide: a time field, then one field per series
            times = f["data"]["values"][0]
            for field, values in zip(f["schema"]["fields"][1:], f["data"]["values"][1:]):
                name = (field.get("labels") or {}).get("metric") or field["name"]
                out[name] = [(t / 1000.0, v) for t, v in zip(times, values) if v is not None]
        return out
    roles = reg.devices[LOOP]["roles"]
    constant = roles["sp_cmd"]
    window = 60
    # Limit 120 s: a window of a minute in which the set point has no row of its own (the tests
    # before restart the logger, whose start writes a gap and the value again)
    S.wait_for(lambda: not q("SELECT 1 FROM changes WHERE pv = %s AND t > now() - interval '65 seconds'", (pv_id(constant),)),
               120, "a minute without a row of %s" % constant)
    asked = time.time()
    held = ask("SELECT * FROM log_trend(ARRAY['%s'], $__timeFrom(), $__timeTo(), $__interval_ms) ORDER BY 1" % constant, window)
    points = next(iter(held.values()))
    through = q("SELECT raw_through FROM state")[0][0].timestamp()
    assert len(points) >= 2 and points[0][0] <= asked - window + 1 and points[-1][0] >= through - 1.5, (points, asked, through)
    assert len({v for _, v in points}) == 1
    # the plasma generator's graph of the loop's measured value: two series, each a line
    with open(os.path.join(BUILD, "dashboards", "plasma-generator.json")) as handle:
        panel = next(p for p in json.load(handle)["panels"] if constant in p["targets"][0]["rawSql"])
    series = ask(panel["targets"][0]["rawSql"], 300)
    assert len(series) == 2 and all(len(v) >= 2 for v in series.values()), {k: len(v) for k, v in series.items()}

    # F8: every series of a panel with several is a line of its own: asked as the dashboard's panel
    # asks (its format, its query), a series holds NULL only at its own gap rows, not at the time
    # stamps of the other series. The truth: the panel's query run in the database directly.
    with open(os.path.join(BUILD, "dashboards", "plasma-generator.json")) as handle:
        multi = [p for p in json.load(handle)["panels"] if p["type"] == "timeseries" and p["targets"][0]["rawSql"].count("), (") >= 1]
    assert multi
    t_to = math.floor(time.time() * 1000) - 5000        # data complete there: both queries see the same rows
    t_from = t_to - 300000
    for panel in multi:
        target = panel["targets"][0]
        step = int(max(minimum * 1000, (t_to - t_from) / 1000))
        body = {"from": str(t_from), "to": str(t_to), "queries": [dict(target, intervalMs=step, maxDataPoints=1000)]}
        req = urllib.request.Request(base + "/api/ds/query", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        frames = json.load(urllib.request.urlopen(req, timeout=10))["results"]["A"]["frames"]
        got = {}
        for f in frames:
            names = [fl["name"] for fl in f["schema"]["fields"]]
            values = f["data"]["values"]
            if "metric" in names:                       # long: one row per point of one series
                for t, m, v in zip(values[0], values[names.index("metric")], values[names.index("value")]):
                    got.setdefault(m, []).append((t, v))
            else:                                       # wide: one field per series
                for fl, vals in zip(f["schema"]["fields"][1:], values[1:]):
                    name = (fl.get("labels") or {}).get("metric") or fl["name"]
                    got.setdefault(name, []).extend(zip(values[0], vals))
        sql = target["rawSql"].replace("$__timeFrom()", "'%s'" % ts(t_from / 1000).isoformat()).replace(
            "$__timeTo()", "'%s'" % ts(t_to / 1000).isoformat()).replace("$__interval_ms", str(step))
        want = {}
        for t, metric, value in q(sql):
            want.setdefault(metric, []).append((math.floor(t.timestamp() * 1000 + 1e-6), value))
        assert set(got) == set(want), (panel["title"], set(got), set(want))
        for name in want:
            own_gaps = {t for t, v in want[name] if v is None}
            nulls = {t for t, v in got[name] if v is None}
            assert nulls <= own_gaps, "%s, %s: NULL at %d time stamps that are no gap of its own" % (
                panel["title"], name, len(nulls - own_gaps))
            assert sum(v is not None for _, v in got[name]) == sum(v is not None for _, v in want[name]), (panel["title"], name)

    # every trend of the generated panels draws from the database (as the read-only user)
    with open(os.path.join(BUILD, "dashboards", "plasma-generator.json")) as handle:
        board = json.load(handle)
    # the registry's trends: the loop's measured value with its set point beside it, its output
    roles = reg.devices[LOOP]["roles"]
    graphs = [p["targets"][0]["rawSql"] for p in board["panels"] if p["type"] == "timeseries"]
    assert any("'%s', '%s'" % (roles["pv"], roles["sp_cmd"]) in g for g in graphs), graphs
    assert any("ARRAY['%s']" % roles["out"] in g for g in graphs), graphs
    now = time.time()
    for panel in board["panels"]:
        sql = panel["targets"][0]["rawSql"]
        if "log_trend" in sql:
            sql = sql.replace("$__timeFrom()", "'%s'" % ts(now - 600).isoformat()).replace(
                "$__timeTo()", "'%s'" % ts(now).isoformat()).replace("$__interval_ms", "1000")
            reader = dict(DSN, user="mist2log_reader", password=os.environ["MIST2LOG_READER_PASSWORD"])
            with psycopg.connect(**reader) as conn:
                assert conn.execute(sql).fetchall(), panel["title"]


# --- R6: load ---------------------------------------------------------------------------------------
def test_load_of_the_full_emulation():
    """Rows per second, CPU and memory of the logger and the database, rows per tier: written
    to logger/build/load.md (LOGGER.md, sizing)."""
    rates = []
    for _ in range(30):
        rates.append(status("rows"))
        time.sleep(1)
    stats = request("stats")
    t1 = time.time() - CLOSE_DELAY - WRITTEN
    t0 = t1 - 300
    per = {}
    for table in ("raw", "changes", "seconds", "minutes", "events"):
        n = q("SELECT count(*) FROM %s WHERE t >= %%s AND t < %%s" % table, (ts(t0), ts(t1)))[0][0]
        size = q("SELECT pg_total_relation_size(%s) + coalesce((SELECT sum(total_bytes) FROM hypertable_detailed_size(%s)), 0)",
                 (table, table))[0][0] if table != "events" else q("SELECT pg_total_relation_size('events')")[0][0]
        rows = q("SELECT count(*) FROM %s" % table)[0][0]
        per[table] = (n / 300.0, size, rows)
    lines = ["| Load of the full emulation (no plant), %s | Value |" % time.strftime("%Y-%m-%d %H:%M"), "|---|---|",
             "| Rows written per second (LOGGER:rows:get, mean of 30 s) | %.1f |" % (sum(rates) / len(rates))]
    for table, (rate, size, rows) in per.items():
        lines.append("| %s: rows per second (last 5 min) / bytes per row on disk (all %d rows, indexes included) | %.2f / %s |"
                     % (table, rows, rate, "%.0f" % (size / rows) if rows else "-"))
    lines.append("| docker stats (CPU, memory) | %s |" % stats.strip().replace("\n", "; "))
    if "stats_outage" in WINDOWS:
        lines.append("| during the minute without database: buffer in use, docker stats | %.2f %% of %s rows; %s |"
                     % (WINDOWS["stats_outage"][0], os.environ.get("MIST2LOG_BUFFER_ROWS", "?"), WINDOWS["stats_outage"][1].strip()))
    text = "\n".join(lines) + "\n"
    with open(os.path.join(BUILD, "load.md"), "w") as handle:
        handle.write(text)
    S.report(text)
    assert per["raw"][0] > 0
