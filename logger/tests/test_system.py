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
        assert [(float(o), float(n)) for o, n in events][:1] == [(old, new)], events
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
    """Mean, min, max per interval from the raw rows, independently of the logger: each value holds
    until the next row, weighted by time; rows before `start` give the value held at it."""
    out = []
    for k in range(count):
        a, b = start + k * width, start + (k + 1) * width
        segs = []
        for i, (t, v) in enumerate(rows):
            end = rows[i + 1][0] if i + 1 < len(rows) else math.inf
            lo, hi = max(t, a), min(end, b)
            if hi > lo:
                segs.append((hi - lo, v))
        total = sum(d for d, _ in segs)
        out.append((a, sum(d * v for d, v in segs) / total, min(v for _, v in segs), max(v for _, v in segs)))
    return out


def test_seconds_and_minutes_of_a_changing_pv_against_the_raw_rows():
    t0, t1 = WINDOWS["fast"]
    rows = [(r[0].timestamp(), r[1]) for r in q(
        "SELECT t, value FROM raw WHERE pv = %s AND t >= %s AND t < %s ORDER BY t", (pv_id(FAST), ts(t0 - 5), ts(t1)))]
    assert all(r[1] is not None for r in rows)
    for table, width in (("seconds", 1), ("minutes", 60)):
        start = math.ceil(t0 / width) * width
        count = int((t1 - start) // width)
        if count == 0:
            continue
        want = expected_intervals(rows, start, width, count)
        got = q("SELECT t, mean, min, max, valid FROM %s WHERE pv = %%s AND t >= %%s AND t < %%s ORDER BY t" % table,
                (pv_id(FAST), ts(start), ts(start + count * width)))
        assert len(got) == count, (table, len(got), count)        # every interval changed: all stored
        for (a, mean, mn, mx), (t, gmean, gmn, gmx, valid) in zip(want, got):
            assert t.timestamp() == a and valid == pytest.approx(1.0)
            assert (gmean, gmn, gmx) == (pytest.approx(mean, rel=1e-9), mn, mx), (table, a)


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
    direct = q("SELECT t, value FROM raw WHERE pv = %s AND t >= %s AND t < %s ORDER BY t", (pv_id(FAST), ts(t0), ts(t1)))
    values = [(datetime.datetime.fromisoformat(r["t"]), float(r["value"])) for r in rows if r["kind"] == "value"]
    assert values == [(t, v) for t, v in direct]
    assert rows[0]["kind"] == "held" and rows[-1]["kind"] == "held"      # the value at both ends
    rows = tool(FAST, "--from", ts(math.ceil(t0)).isoformat(), "--to", ts(math.floor(t1)).isoformat(), "--tier", "seconds")
    direct = q("SELECT t, mean, min, max FROM seconds WHERE pv = %s AND t >= %s AND t < %s ORDER BY t",
               (pv_id(FAST), ts(math.ceil(t0)), ts(math.floor(t1))))
    assert [(datetime.datetime.fromisoformat(r["t"]), float(r["value"]), float(r["min"]), float(r["max"])) for r in rows] == direct
    name, a, b = WINDOWS["gap"]
    rows = tool(name, "--from", ts(a).isoformat(), "--to", ts(b).isoformat())
    assert rows and {r["kind"] for r in rows} == {"gap"} and {r["value"] for r in rows} == {""}


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
    request("buffer 3000")        # rows: about 20 s of the full emulation (140 rows per second)
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
def test_grafana_answers_and_has_one_dashboard_per_page_of_the_gui():
    base = "http://127.0.0.1:%s" % os.environ["MIST2LOG_GRAFANA_PORT"]
    health = json.load(urllib.request.urlopen(base + "/api/health", timeout=5))
    assert health["database"] == "ok"
    installed = [d for d, dev in reg.devices.items() if not dev["flags"].get("not_installed")]
    pages = ["Overview"] + list(dict.fromkeys(reg.devices[d]["page"] for d in installed)) + ["Trends", "Infrastructure"]
    # Limit 40 s: Grafana rereads the dashboard files every 30 s
    def titles():
        found = json.load(urllib.request.urlopen(base + "/api/search?type=dash-db", timeout=5))
        return sorted(b["title"] for b in found)
    S.wait_for(lambda: titles() == sorted(pages), 40, lambda: "dashboards %s, pages %s" % (titles(), pages))
    # every trend of the generated panels draws from the database (as the read-only user)
    with open(os.path.join(BUILD, "dashboards", "plasma-generator.json")) as handle:
        board = json.load(handle)
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
