"""The database side of the logger: schema, life times, and a writer thread with a bounded buffer.

The main thread hands over one Batch per tick (put). The writer writes the batches in their
order, each in one transaction together with the state row (how far the data is complete).
While the database is lost or slow the batches wait in the buffer; a batch that does not fit is
not kept: its rows are counted, and when the database is back the logger writes a gap from the
end of what was written, an event with the count, and the present state of every PV (resume).
"""
import collections
import datetime
import logging
import os
import threading
import time

import psycopg
from psycopg import sql

log = logging.getLogger("mist2log.store")
UTC = datetime.timezone.utc
TABLE_TIER = {"raw": "raw", "changes": "events", "seconds": "seconds", "minutes": "minutes"}
# Size of the chunks of each table: data is dropped by whole chunks, so a row lives at most its
# life time plus one chunk. Our choice: a twentieth to a tenth of the life time, few chunks for ever.
CHUNKS = {"raw": "1 day", "changes": "30 days", "seconds": "30 days", "minutes": "365 days"}
SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def ts(t):
    return datetime.datetime.fromtimestamp(t, UTC)


def posix(d):
    return d.timestamp() if d is not None else None


def connect(dsn, **kw):
    return psycopg.connect(connect_timeout=5, keepalives=1, keepalives_idle=5, keepalives_interval=2,
                           keepalives_count=2, **dict(dsn, **kw))


def apply_schema(conn, tiers, chunks=None, reader_password=""):
    """Tables, functions, chunk sizes and life times (keep_days of each tier; None: for ever)."""
    chunks = chunks or CHUNKS
    with conn.cursor() as cur:
        cur.execute(open(SCHEMA, encoding="utf-8").read())
        for tid, spec in tiers.items():
            cur.execute("INSERT INTO tier (id, interval, keep_days) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE "
                        "SET interval = excluded.interval, keep_days = excluded.keep_days",
                        (tid, spec["interval"], spec["keep_days"]))
        for table, tier in TABLE_TIER.items():
            cur.execute("SELECT set_chunk_time_interval(%s, %s::interval)", (table, chunks[table]))
            cur.execute("SELECT remove_retention_policy(%s, if_exists => true)", (table,))
            keep = tiers[tier]["keep_days"]
            if keep is not None:
                cur.execute("SELECT add_retention_policy(%s, %s * interval '1 day')", (table, keep))
        if reader_password:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'mist2log_reader'")
            if not cur.fetchone():
                cur.execute("CREATE ROLE mist2log_reader LOGIN")
            cur.execute(sql.SQL("ALTER ROLE mist2log_reader PASSWORD {}").format(sql.Literal(reader_password)))
            cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO mist2log_reader")
            cur.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mist2log_reader")
    conn.commit()


class Store:
    def __init__(self, settings, tiers):
        self.dsn, self.tiers, self.limit = settings.db, tiers, settings.buffer_rows
        self.reader_password = settings.reader_password
        self.conn = None
        self.cond = threading.Condition()
        self.queue = collections.deque()
        self.buffered = 0                # rows in the queue
        self.accepted_through = None     # through of the last batch accepted into the queue
        self.written_through = None      # through of the last batch written
        self.lost = None                 # [through of the last kept batch, first time lost, rows]
        self.dropped = 0                 # rows lost since the start
        self.rejected = []               # [through before it, its time, rows, message]: batches the database refused
        self.db_ok = False
        self.written = collections.deque(maxlen=10)    # (time, rows) of the last writes
        self.stopping = False
        self.thread = None

    # --- start ------------------------------------------------------------------------------------
    def open(self, channels):
        """Wait for the database, apply the schema, register the PVs. Returns ({name: id},
        through of the last run or None, {id: (severity, value text)}, last alive)."""
        while True:
            try:
                self.conn = connect(self.dsn)
                apply_schema(self.conn, self.tiers, reader_password=self.reader_password)
                break
            except psycopg.Error as exc:
                log.warning("database not reachable (%s), trying again in 2 s", str(exc).strip())
                self._close()
                time.sleep(2)
        with self.conn.cursor() as cur:
            ids = {}
            for ch in channels:
                cur.execute("INSERT INTO pv (name, tier, kind, type, egu, states, device, role, driven_by) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (name) DO UPDATE SET "
                            "tier = excluded.tier, kind = excluded.kind, type = excluded.type, egu = excluded.egu, "
                            "states = excluded.states, device = excluded.device, role = excluded.role, "
                            "driven_by = excluded.driven_by RETURNING id",
                            (ch.name, ch.tier, ch.kind, ch.type, ch.egu, ch.states, ch.device, ch.role,
                             ch.driver[0] if ch.driver else None))
                ids[ch.name] = cur.fetchone()[0]
            cur.execute("UPDATE pv SET connected = false")
            cur.execute("SELECT raw_through, seconds_through, minutes_through, alive FROM state WHERE id = 1")
            row = cur.fetchone()
            through = tuple(posix(x) for x in row[:3]) if row and row[0] is not None else None
            alive = posix(row[3]) if row else None
            cur.execute("SELECT id, severity, value_text FROM pv")
            known = {i: (s, v) for i, s, v in cur.fetchall()}
        self.conn.commit()
        self.db_ok = True
        self.written_through = through
        return ids, through, known, alive

    def start(self):
        self.thread = threading.Thread(target=self._run, name="writer", daemon=True)
        self.thread.start()

    # --- main thread ----------------------------------------------------------------------------
    def put(self, batch, force=False):
        with self.cond:
            n = batch.rows()
            if not force and (self.lost is not None or self.buffered + n > self.limit):
                if self.lost is None:
                    self.lost = [self.accepted_through or self.written_through, batch.now, 0]
                    log.error("buffer full (%d rows): rows are lost until the database takes them", self.buffered)
                self.lost[2] += n
                self.dropped += n
                return
            batch.counted = n
            self.queue.append(batch)
            self.buffered += n
            self.accepted_through = batch.through or self.accepted_through
            self.cond.notify()

    def take_loss(self):
        """When the rows lost are behind us (the buffer is empty again): (through, first lost, rows), once."""
        with self.cond:
            if self.lost is None or self.queue or not self.db_ok:
                return None
            lost, self.lost = self.lost, None
            return lost

    def take_rejected(self):
        """The batches the database refused since the last call: [(through, time, rows, message)]."""
        with self.cond:
            out, self.rejected = self.rejected, []
            return out

    def status(self):
        with self.cond:
            now = time.time()
            rows = sum(n for t, n in self.written if t > now - 10)
            return {"db": self.db_ok, "buffer": 100.0 * self.buffered / self.limit if self.limit else 0.0,
                    "rows": rows / 10.0, "dropped": self.dropped}

    def close(self, timeout=10.0):
        """Write what is left (for at most timeout seconds) and stop the writer."""
        end = time.time() + timeout
        with self.cond:
            while self.queue and time.time() < end:
                self.cond.wait(0.2)
            self.stopping = True
            self.cond.notify()
        if self.thread:
            self.thread.join(2)
        self._close()

    # --- writer thread --------------------------------------------------------------------------
    def _run(self):
        while True:
            with self.cond:
                while not self.queue and not self.stopping:
                    self.cond.wait(1.0)
                if self.stopping:
                    return
                batch = self.queue[0]
            try:
                if self.conn is None:
                    self.conn = connect(self.dsn)
                    if not self.db_ok:
                        batch.events.append((time.time(), None, "logger", None, "database back", None, None, None, None))
                self._write(batch)
                with self.cond:
                    self.queue.popleft()
                    self.buffered -= batch.counted
                    self.written_through = batch.through or self.written_through
                    self.written.append((time.time(), batch.rows()))
                    self.db_ok = True
                    self.cond.notify_all()
            except (psycopg.DataError, psycopg.IntegrityError) as exc:
                # The database answered and refuses this batch: trying it again would block the
                # writer for ever. Give it up, count its rows, and go on with the next batch.
                log.error("database refused a batch of %d rows: %s", batch.counted, str(exc).strip())
                try:
                    self.conn.rollback()
                except psycopg.Error:
                    self._close()
                with self.cond:
                    self.queue.popleft()
                    self.buffered -= batch.counted
                    self.dropped += batch.counted
                    self.rejected.append((self.written_through, batch.now, batch.counted, str(exc).strip()[:300]))
                    self.cond.notify_all()
            except (psycopg.Error, OSError) as exc:
                if self.db_ok:
                    log.error("database lost: %s", str(exc).strip())
                    with self.cond:
                        self.db_ok = False
                        batch.events.append((time.time(), None, "logger", None, "database lost", None, None, None,
                                             str(exc).strip()[:200]))
                self._close()
                time.sleep(1.0)

    def _close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:              # noqa: BLE001  closing a broken connection
                pass
        self.conn = None

    def _write(self, b):
        with self.conn.cursor() as cur:
            for table in ("raw", "changes"):
                rows = getattr(b, table)
                if rows:
                    with cur.copy("COPY %s (pv, t, value, text, severity, status, flags) FROM STDIN" % table) as copy:
                        for pv, t, value, text, sev, stat, flags in rows:
                            copy.write_row((pv, ts(t), value, text, sev, stat, flags))
            for table in ("seconds", "minutes"):
                rows = getattr(b, table)
                if rows:
                    cols = list(zip(*rows))
                    cur.execute(
                        "INSERT INTO %s SELECT * FROM unnest(%%s::int[], %%s::timestamptz[], %%s::float8[], %%s::float8[], "
                        "%%s::float8[], %%s::real[], %%s::smallint[], %%s::float8[], %%s::smallint[]) "
                        "ON CONFLICT (pv, t) DO UPDATE SET mean = excluded.mean, min = excluded.min, max = excluded.max, "
                        "valid = excluded.valid, severity = excluded.severity, last = excluded.last, "
                        "last_severity = excluded.last_severity" % table,
                        [list(cols[0]), [ts(t) for t in cols[1]]] + [list(c) for c in cols[2:]])
            if b.events:
                with cur.copy("COPY events (t, pv, kind, old, new, value, severity, status, detail) FROM STDIN") as copy:
                    for row in b.events:
                        copy.write_row((ts(row[0]),) + tuple(row[1:]))
                for t, pv, kind, old, new, value, sev, stat, detail in b.events:
                    if pv is None:
                        continue
                    if kind == "alarm":
                        cur.execute("UPDATE pv SET severity = %s WHERE id = %s", (sev, pv))
                    elif kind in ("set", "state"):
                        cur.execute("UPDATE pv SET value_text = %s WHERE id = %s", (new, pv))
            for pv, up, t in b.connections:
                cur.execute("UPDATE pv SET connected = %s, since = %s WHERE id = %s", (up, ts(t), pv))
            if b.through:
                cur.execute("INSERT INTO state (id, started, alive, raw_through, seconds_through, minutes_through) "
                            "VALUES (1, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET alive = excluded.alive, "
                            "raw_through = excluded.raw_through, seconds_through = excluded.seconds_through, "
                            "minutes_through = excluded.minutes_through"
                            + (", started = excluded.started" if b.started else ""),
                            (ts(b.started or b.now), ts(b.now)) + tuple(ts(x) for x in b.through))
        self.conn.commit()
