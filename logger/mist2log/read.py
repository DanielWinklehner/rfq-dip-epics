"""Read logged data: a module for notebooks and training, and a command line tool.

    python -m mist2log.read TDK:current:read --from "2026-11-22 14:00" --to "2026-11-22 15:00"
    python -m mist2log.read TDK:current:read REK-1:current:read --last 1h --tier seconds -o run.csv
    python -m mist2log.read --events --last 1d

In Python:

    from mist2log.read import Reader
    with Reader() as r:
        rows = r.read("TDK:current:read", "2026-11-22 14:00", "2026-11-22 15:00", tier="best")

A row: t (datetime, UTC), value (the value, or the interval's mean), min, max, text (word of an
enumeration, or the text), severity, valid (share of the interval with a valid value), kind
('value': stored, 'held': the value in effect, 'gap': no valid value), tier. The reader hides
how constant values and gaps are stored: a value that holds is returned where it holds (at the
start of the range, and again where its stretch ends: at the next gap or at the end), and a gap
is a row of kind 'gap' with value None. Tiers: raw, seconds, minutes, events, or best (the
finest tier the PV is kept in that covers the range in at most max_points rows).

Connection: the environment variables MIST2LOG_DB_HOST, _PORT, _NAME, and MIST2LOG_READ_USER and
MIST2LOG_READ_PASSWORD (default: the read-only role mist2log_reader and MIST2LOG_READER_PASSWORD).
"""
import argparse
import csv
import datetime
import os
import re
import sys

import psycopg

UTC = datetime.timezone.utc
COLUMNS = ("t", "value", "min", "max", "text", "severity", "valid", "kind", "tier")
EVENT_COLUMNS = ("t", "kind", "pv", "device", "old", "new", "value", "severity", "detail")


def dsn():
    env = os.environ.get
    return {"host": env("MIST2LOG_DB_HOST") or "127.0.0.1", "port": int(env("MIST2LOG_DB_PORT") or 5432),
            "dbname": env("MIST2LOG_DB_NAME") or "mist2log",
            "user": env("MIST2LOG_READ_USER") or "mist2log_reader",
            "password": env("MIST2LOG_READ_PASSWORD") or env("MIST2LOG_READER_PASSWORD") or ""}


def when(text):
    """A time: datetime, POSIX seconds, ISO text (local time if it has no zone), or 'now'."""
    if isinstance(text, datetime.datetime):
        return text if text.tzinfo else text.astimezone()
    if isinstance(text, (int, float)):
        return datetime.datetime.fromtimestamp(text, UTC)
    if text == "now":
        return datetime.datetime.now(UTC)
    d = datetime.datetime.fromisoformat(text)
    return d if d.tzinfo else d.astimezone()


def span(text):
    """'90s', '10m', '2h', '1d' -> timedelta."""
    found = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd])", text)
    if not found:
        raise argparse.ArgumentTypeError("a duration like 90s, 10m, 2h or 1d")
    return datetime.timedelta(seconds=float(found.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[found.group(2)])


class Reader:
    def __init__(self, **connection):
        self.conn = psycopg.connect(**dict(dsn(), **connection))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.conn.close()

    def read(self, pv, start, end, tier="best", max_points=20000):
        """Rows of one PV in [start, end) as dicts (COLUMNS)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM log_read(%s, %s, %s, %s, %s)", (pv, when(start), when(end), tier, max_points))
            rows = [dict(zip(COLUMNS, row)) for row in cur.fetchall()]
        self.conn.commit()
        return rows

    def events(self, start, end, pvs=None, kinds=None):
        """The event log in [start, end), optionally of some PVs or kinds, as dicts (EVENT_COLUMNS)."""
        query = "SELECT %s FROM event_log WHERE t >= %%s AND t < %%s" % ", ".join(EVENT_COLUMNS)
        args = [when(start), when(end)]
        if pvs:
            query += " AND pv = ANY(%s)"
            args.append(list(pvs))
        if kinds:
            query += " AND kind = ANY(%s)"
            args.append(list(kinds))
        with self.conn.cursor() as cur:
            cur.execute(query + " ORDER BY t", args)
            rows = [dict(zip(EVENT_COLUMNS, row)) for row in cur.fetchall()]
        self.conn.commit()
        return rows

    def pvs(self):
        """Every logged PV: {name: tier}."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT name, tier FROM pv WHERE tier <> 'none' ORDER BY name")
            return dict(cur.fetchall())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pvs", nargs="*", help="PV names (none with --events or --list)")
    parser.add_argument("--from", dest="start", type=when, help="start (ISO time, local unless it has a zone)")
    parser.add_argument("--to", dest="end", type=when, default=when("now"), help="end (default: now)")
    parser.add_argument("--last", type=span, help="instead of --from: this long before --to (90s, 10m, 2h, 1d)")
    parser.add_argument("--tier", default="best", choices=["best", "raw", "seconds", "minutes", "events"])
    parser.add_argument("--max-points", type=int, default=20000, help="for --tier best (default 20000)")
    parser.add_argument("--events", action="store_true", help="the event log (of the PVs given, or all)")
    parser.add_argument("--list", action="store_true", help="the logged PVs and their tiers")
    parser.add_argument("-o", "--output", help="CSV file (default: standard output)")
    args = parser.parse_args(argv)
    out = open(args.output, "w", newline="") if args.output else sys.stdout
    writer = csv.writer(out)
    with Reader() as reader:
        if args.list:
            writer.writerow(("pv", "tier"))
            writer.writerows(reader.pvs().items())
            return 0
        if args.start is None:
            if args.last is None:
                parser.error("give --from or --last")
            args.start = args.end - args.last
        if args.events:
            writer.writerow(EVENT_COLUMNS)
            for row in reader.events(args.start, args.end, args.pvs or None):
                writer.writerow([row["t"].isoformat()] + [row[c] for c in EVENT_COLUMNS[1:]])
            return 0
        if not args.pvs:
            parser.error("name at least one PV")
        writer.writerow(("pv",) + COLUMNS)
        for pv in args.pvs:
            for row in reader.read(pv, args.start, args.end, args.tier, args.max_points):
                writer.writerow([pv, row["t"].isoformat()] + [row[c] for c in COLUMNS[1:]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
