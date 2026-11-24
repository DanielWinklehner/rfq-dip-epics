"""The files of one scan: one directory with points.csv, scan.json and definition.yaml.

points.csv  one row per point, written and flushed to disk as soon as the point is done
scan.json   the scan as it ran: definition, times, PV units and limits, how and why it ended,
            where the actuator was left. Written at the start (state "running") and replaced
            at the end, so a scan killed hard still says "running"
definition.yaml  the definition as it ran (overrides applied): runs the same scan again

Plain text: csv and json from the standard library, readable by numpy and pandas. No EPICS.
"""
import csv
import datetime
import json
import math
import os
import re

import yaml

FIELDS = ("mean", "spread", "n", "min", "max", "valid", "status", "reason")


def columns(channel_names):
    cols = ["point", "time", "elapsed_s", "set", "outcome"]
    for name in channel_names:
        cols += ["%s_%s" % (name, f) for f in FIELDS]
    return cols


def iso(t):
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="milliseconds")


def number(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "nan"
    if isinstance(x, int):
        return str(x)
    return repr(float(x))


class ScanFiles:
    def __init__(self, base, name, wall_time):
        stamp = datetime.datetime.fromtimestamp(wall_time).strftime("%Y%m%d-%H%M%S")
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "scan"
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, "%s-%s" % (safe, stamp))
        n = 1
        while True:
            try:
                os.mkdir(path)
                break
            except FileExistsError:
                n += 1
                path = os.path.join(base, "%s-%s-%d" % (safe, stamp, n))
        self.path = path
        self.table = None
        self.writer = None
        self.rows = 0

    def start(self, definition_data, channel_names, meta):
        with open(os.path.join(self.path, "definition.yaml"), "w", encoding="utf-8") as handle:
            handle.write("# The definition as it ran (overrides applied). %s\n" % meta["start_time"])
            yaml.safe_dump(definition_data, handle, sort_keys=False, default_flow_style=False)
        self.table = open(os.path.join(self.path, "points.csv"), "w", encoding="utf-8",
                          newline="")
        self.writer = csv.writer(self.table, lineterminator="\n")
        self.cols = columns(channel_names)
        self.writer.writerow(self.cols)
        self._sync()
        self.meta(meta)

    def row(self, point, wall_time, elapsed, set_value, outcome, summaries):
        """summaries: one stats.Summary per channel, in the order of the header."""
        out = [str(point), iso(wall_time), "%.3f" % elapsed, number(set_value), outcome]
        for s in summaries:
            out += [number(s.mean), number(s.spread), str(s.n), number(s.minimum),
                    number(s.maximum), "%.3f" % s.valid, s.status, s.reason]
        self.writer.writerow(out)
        self._sync()
        self.rows += 1

    def _sync(self):
        self.table.flush()
        os.fsync(self.table.fileno())

    def meta(self, meta):
        path = os.path.join(self.path, "scan.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(_no_nan(meta), handle, indent=2, default=_plain)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def close(self):
        if self.table is not None:
            self.table.close()
            self.table = None


def _no_nan(x):
    """NaN is not JSON: null instead."""
    if isinstance(x, dict):
        return {k: _no_nan(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_no_nan(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def _plain(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return str(x)
