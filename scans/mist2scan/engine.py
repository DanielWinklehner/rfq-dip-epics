"""The scan: refusals, one point after the other, every end. No EPICS import.

`io` is the Channel Access side (ca.py; a fake one in the tests). It calls on_value and
on_connection from its own threads (monitors); the scan reads what they left under a lock and
writes through io.write, only to the set PV, only within the limits. Times come from `clock`
(monotonic seconds) and `wall` (time.time), waiting from `sleep`: the tests replace all three.

One point (docs/emulation/SCAN.md, section 2):
  1. move: write the point, in part steps of at most max_step with step_pause between them;
  2. settle: wait until the read-back is valid and within the tolerance, at most settle_timeout;
  3. wait settle_time more;
  4. dwell: read each channel fresh, then take every monitor update for `dwell` seconds;
     nothing that arrived before this step is used;
  5. one row: per channel the time-weighted mean, spread, number of values, minimum, maximum,
     the valid fraction, ok/partial/missing and why.
Between any two steps, every TICK while waiting: a stop signal, the actuator or a required
detector not connected, the set PV INVALID or a condition that does not hold ends the scan.
"""
import logging
import math
import os
import platform
import socket
import sys
import threading
import time
import traceback

from . import VERSION
from .definition import part_steps
from .files import iso
from .stats import MISSING, missing, summarize

INVALID = 3
TICK = 0.05

# Exit codes (docs/emulation/SCAN.md, section 5)
COMPLETED = 0
DEFINITION = 2
REFUSED = 3
CONDITION = 4
ACTUATOR = 5
DETECTOR = 6
NOT_SETTLED = 7
ERROR = 8
SIGINT = 130
SIGTERM = 143
REASONS = {COMPLETED: "completed", DEFINITION: "definition error", REFUSED: "refused",
           CONDITION: "condition lost", ACTUATOR: "actuator lost",
           DETECTOR: "required detector lost", NOT_SETTLED: "not settled",
           ERROR: "program error", SIGINT: "interrupted (SIGINT, ctrl-c)",
           SIGTERM: "terminated (SIGTERM)"}

log = logging.getLogger("mist2scan")


class Reading:
    """One value of a PV as Channel Access delivered it: value, severity, IOC time stamp."""

    __slots__ = ("value", "severity", "stamp")

    def __init__(self, value, severity, stamp=None):
        self.value, self.severity, self.stamp = value, severity, stamp

    def __repr__(self):
        return "Reading(%r, %r, %r)" % (self.value, self.severity, self.stamp)


def problem(reading, absent="not connected"):
    """Why a reading cannot be used, or None when it can."""
    if reading is None:
        return absent
    if reading.severity is None:
        return "no alarm state"
    if reading.severity >= INVALID:
        return "INVALID"
    try:
        value = float(reading.value)
    except (TypeError, ValueError):
        return "not a number"
    if not math.isfinite(value):
        return "not a number"
    return None


class End(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, detail)
        self.code, self.detail = code, detail


class Refused(Exception):
    def __init__(self, reasons, plan=None):
        Exception.__init__(self, "; ".join(reasons))
        self.reasons, self.plan = reasons, plan


class Scan:
    def __init__(self, definition, io, clock=time.monotonic, sleep=time.sleep, wall=time.time,
                 tick=TICK):
        self.d = definition
        self.io = io
        self.clock, self.sleep, self.wall, self.tick = clock, sleep, wall, tick
        self.lock = threading.Lock()
        self.latest = {}             # PV -> Reading of the last monitor update (None: lost)
        self.connected = {}          # PV -> bool, from the connection callbacks
        self.windows = None          # during a dwell: PV -> [(time, Reading or None)]
        self.stop_signal = None
        self.ending = False
        self.position = None         # the last value written (at the start: the set PV's)
        self.writes = []             # (wall time, value, phase) of every write
        self.point = None
        self.phase = "prepare"
        self.plan = None
        self.files = None
        self.meta = None

    # --- called by the Channel Access side, from its threads -------------------------------

    def on_value(self, name, reading):
        with self.lock:
            t = self.clock()
            self.connected[name] = True
            self.latest[name] = reading
            if self.windows is not None and name in self.windows:
                self.windows[name].append((t, reading))

    def on_connection(self, name, up):
        with self.lock:
            t = self.clock()
            self.connected[name] = up
            if not up:
                self.latest[name] = None
                if self.windows is not None and name in self.windows:
                    self.windows[name].append((t, None))

    def request_stop(self, signum):
        """From the signal handler. During the end move a signal changes nothing: the move
        back is what the first signal asked for."""
        if self.ending:
            log.warning("signal %d during the end move: ignored, the move goes on", signum)
        elif self.stop_signal is None:
            self.stop_signal = signum

    # --- before the start -----------------------------------------------------------------

    def prepare(self):
        """Connect, read, check. Returns the plan (a dict), or raises Refused with every reason
        found. Writes nothing."""
        d = self.d
        names = d.pvs()
        self.io.open(names, self.on_value, self.on_connection)
        absent = set(self.io.wait_connected(names, d.connect_timeout))
        with self.lock:
            for n in names:
                self.connected.setdefault(n, n not in absent)
        reads = {}
        for n in names:
            reads[n] = None if n in absent else self.io.read(n)
        with self.lock:
            for n, r in reads.items():
                if self.latest.get(n) is None and r is not None:
                    self.latest[n] = r
        reasons, warnings = [], []

        def why(n):
            return problem(reads[n], "not connected" if n in absent else "no answer")

        for role, n in (("set PV", d.set_pv), ("read-back", d.readback_pv)):
            if why(n):
                reasons.append("actuator %s %s: %s" % (role, n, why(n)))
        for det in d.detectors:
            if why(det.pv):
                text = "detector %s (%s): %s" % (det.name, det.pv, why(det.pv))
                (reasons if det.required else warnings).append(
                    text + ("" if det.required else " (optional: its points will be missing)"))
        for c in d.conditions:
            if why(c.pv):
                reasons.append("condition %s: %s" % (c.text(), why(c.pv)))
            elif not c.holds(reads[c.pv].value):
                reasons.append("condition %s does not hold: %s is %g"
                               % (c.text(), c.pv, float(reads[c.pv].value)))

        info = {n: (self.io.info(n) if n not in absent else None) for n in names}
        ctrl = None
        set_info = info.get(d.set_pv) or {}
        lo, hi = set_info.get("lower_ctrl_limit"), set_info.get("upper_ctrl_limit")
        if lo is not None and hi is not None and float(hi) > float(lo):
            ctrl = (float(lo), float(hi))
        limits = d.limits
        if ctrl is not None:
            limits = (max(limits[0], ctrl[0]), min(limits[1], ctrl[1]))
            if limits[0] > limits[1]:
                reasons.append("the definition's limits [%g, %g] and the set PV's control limits "
                               "[%g, %g] do not overlap" % (d.limits + ctrl))
        elif d.set_pv not in absent:
            warnings.append("the set PV %s reports no control limits (DRVL = DRVH): only the "
                            "definition's limits apply" % d.set_pv)

        before = reads.get(d.set_pv)
        before_set = None if problem(before) else float(before.value)
        rb = reads.get(d.readback_pv)
        before_rb = None if problem(rb) else float(rb.value)
        lo, hi = limits

        def outside(x):
            return not lo <= x <= hi

        if before_set is not None and outside(before_set):
            reasons.append("the set PV is at %g, outside the limits [%g, %g]: every move from "
                           "there would leave them" % (before_set, lo, hi))
        bad = [x for x in d.points if outside(x)]
        if bad:
            reasons.append("%d of %d points outside the limits [%g, %g], the first %g"
                           % (len(bad), len(d.points), lo, hi, bad[0]))
        if d.end == "previous":
            end_target = before_set
        elif d.end == "stay":
            end_target = None
        else:
            end_target = d.end
            if outside(end_target):
                reasons.append("end value %g outside the limits [%g, %g]" % (end_target, lo, hi))

        plan = {
            "points": list(d.points),
            "limits": {"definition": list(d.limits), "control": list(ctrl) if ctrl else None,
                       "effective": [lo, hi]},
            "before": {"set": before_set, "readback": before_rb},
            "end_target": end_target,
            "pvs": {n: _info(info[n], n in absent) for n in names},
            "warnings": warnings,
            "estimate_s": self.estimate(before_set, end_target),
        }
        self.plan = plan
        if reasons:
            raise Refused(reasons, plan)
        self.position = before_set
        self.limits = (lo, hi)
        return plan

    def estimate(self, start, end_target):
        """(least, most) seconds: moves, settle_time and dwell; the most adds settle_timeout per
        point and for the end."""
        d = self.d
        t, pos = 0.0, start
        for x in d.points:
            if pos is not None:
                t += (len(part_steps(pos, x, d.max_step)) - 1) * d.step_pause
            pos = x
        t += len(d.points) * (d.settle_time + d.dwell)
        if end_target is not None and pos is not None:
            t += (len(part_steps(pos, end_target, d.max_step)) - 1) * d.step_pause
        return [t, t + (len(d.points) + 1) * d.settle_timeout]

    # --- the scan --------------------------------------------------------------------------

    def run(self, make_files, command=None):
        """prepare(), then every point, then the end. Returns the exit code. Refused propagates
        (nothing was written)."""
        plan = self.prepare()
        for w in plan["warnings"]:
            log.warning("%s", w)
        start = self.wall()
        self.t_start = self.clock()
        self.files = make_files(self.d.name, start)
        self.channels = [("readback", self.d.readback_pv)] + [(x.name, x.pv)
                                                              for x in self.d.detectors]
        self.meta = self._meta(plan, start, command)
        self.files.start(self.d.data, [c[0] for c in self.channels], self.meta)
        log.info("scan %s: %d points, files in %s", self.d.name or "(no name)",
                 len(plan["points"]), self.files.path)
        try:
            self._points()
            end = End(COMPLETED, "all %d points done" % len(self.d.points))
        except End as exc:
            end = exc
        except KeyboardInterrupt:
            end = End(SIGINT, "KeyboardInterrupt")
        except Exception:
            end = End(ERROR, traceback.format_exc())
        self._finish(end)
        return end.code

    def _points(self):
        d = self.d
        for i, x in enumerate(d.points):
            self.point = i
            self.phase = "move"
            self._move(x)
            self.phase = "settle"
            if not self._settle(x):
                r = self.latest.get(d.readback_pv)
                last = "last read-back %s" % ("%g" % float(r.value) if not problem(r)
                                              else problem(r))
                sums = [missing("not settled within %g s, %s" % (d.settle_timeout, last))]
                sums += [missing("not settled") for _ in d.detectors]
                self._row(i, x, "not_settled", sums)
                log.warning("point %d at %g: not settled within %g s (%s)", i, x,
                            d.settle_timeout, last)
                if d.on_not_settled == "end":
                    raise End(NOT_SETTLED, "point %d at %g: read-back not within %g of it after "
                              "%g s (%s)" % (i, x, d.tolerance, d.settle_timeout, last))
                continue
            self.phase = "settle_time"
            self._wait(d.settle_time)
            self.phase = "dwell"
            sums = self._collect()
            rb = sums[0]
            outcome = "ok"
            if rb.n and (abs(rb.minimum - x) > d.tolerance or abs(rb.maximum - x) > d.tolerance):
                outcome = "readback_left_tolerance"
            self._row(i, x, outcome, sums)
            log.info("point %d/%d set %g: %s", i + 1, len(d.points), x,
                     "; ".join("%s %s" % (name, _short(s)) for (name, _), s
                               in zip(self.channels, sums)))
            for det, s in zip(d.detectors, sums[1:]):
                if det.required and s.status == MISSING:
                    raise End(DETECTOR, "required detector %s (%s): no valid value at point %d "
                              "(%s)" % (det.name, det.pv, i, s.reason))

    def _row(self, i, x, outcome, sums):
        self.files.row(i, self.wall(), self.clock() - self.t_start, x, outcome, sums)

    def _write(self, value):
        lo, hi = self.limits
        if not lo <= value <= hi:        # prepare() makes this impossible; never write it
            raise RuntimeError("not written: %r outside the limits [%g, %g]" % (value, lo, hi))
        if not self.io.write(self.d.set_pv, value):
            raise End(ACTUATOR, "the write of %g to %s failed (not connected)"
                      % (value, self.d.set_pv))
        self.position = value
        self.writes.append((self.wall(), value, self.phase))
        log.debug("wrote %s = %g (%s)", self.d.set_pv, value, self.phase)

    def _move(self, x):
        steps = part_steps(self.position, x, self.d.max_step)
        for k, v in enumerate(steps):
            self._check()
            self._write(v)
            if k + 1 < len(steps):
                self._wait(self.d.step_pause)

    def _settle(self, x):
        t0 = self.clock()
        while True:
            self._check()
            with self.lock:
                r = self.latest.get(self.d.readback_pv)
            if not problem(r) and abs(float(r.value) - x) <= self.d.tolerance:
                return True
            if self.clock() - t0 >= self.d.settle_timeout:
                return False
            self.sleep(self.tick)

    def _wait(self, seconds):
        end = self.clock() + seconds
        while True:
            self._check()
            left = end - self.clock()
            if left <= 0:
                return
            self.sleep(min(self.tick, left))

    def _check(self):
        """Raises End when the scan cannot go on."""
        d = self.d
        if self.stop_signal is not None:
            code = SIGTERM if self.stop_signal == 15 else SIGINT
            raise End(code, "signal %d" % self.stop_signal)
        with self.lock:
            connected = dict(self.connected)
            latest = dict(self.latest)
        for role, n in (("set PV", d.set_pv), ("read-back", d.readback_pv)):
            if not connected.get(n):
                raise End(ACTUATOR, "actuator %s %s not connected" % (role, n))
        r = latest.get(d.set_pv)
        if r is not None and r.severity is not None and r.severity >= INVALID:
            raise End(ACTUATOR, "actuator set PV %s INVALID: the IOC did not confirm the write"
                      % d.set_pv)
        for det in d.detectors:
            if det.required and not connected.get(det.pv):
                raise End(DETECTOR, "required detector %s (%s) not connected"
                          % (det.name, det.pv))
        for c in d.conditions:
            r = latest.get(c.pv)
            why = problem(r) if connected.get(c.pv) else "not connected"
            if why:
                raise End(CONDITION, "condition %s: %s" % (c.text(), why))
            if not c.holds(r.value):
                raise End(CONDITION, "condition %s no longer holds: %s is %g"
                          % (c.text(), c.pv, float(r.value)))

    def _collect(self):
        """The dwell: a fresh read of every channel when it starts, then the monitor updates
        until it ends. Returns one Summary per channel."""
        pvs = [pv for _, pv in self.channels]
        t0 = self.clock()
        with self.lock:
            self.windows = {pv: [] for pv in pvs}
            connected = dict(self.connected)
        first = {}
        try:
            for pv in pvs:
                first[pv] = self.io.read(pv) if connected.get(pv) else None
            self._wait(self.d.dwell)
            t1 = self.clock()
        finally:
            with self.lock:
                windows, self.windows = self.windows, None
        out = []
        for pv in pvs:
            f = first[pv]
            samples = [(t0, f, "not connected" if not connected.get(pv) else "no answer")]
            gap = f is None
            for t, r in windows[pv]:
                if r is None:
                    samples.append((t, None, "not connected"))
                    gap = True
                elif (gap or r.stamp is None or f.stamp is None
                      or r.stamp > f.stamp):    # not the processing the fresh read already got
                    samples.append((t, r, None))
            plain = []
            for t, r, absent in samples:
                why = problem(r, absent)
                plain.append((t, None if why else float(r.value), why))
            out.append(summarize(plain, t0, t1))
        return out

    # --- the end ---------------------------------------------------------------------------

    def _finish(self, end):
        self.ending = True
        d = self.d
        phase, point = self.phase, self.point
        self.phase = "end"
        target = self.plan["end_target"]
        notes = []
        writes_before = len(self.writes)
        reached = None
        if end.code == ACTUATOR:
            notes.append("the actuator was lost: nothing written after it")
        elif target is None:
            notes.append("end: stay, nothing written")
        else:
            try:
                steps = [] if self.position == target else part_steps(self.position, target,
                                                                      d.max_step)
                for k, v in enumerate(steps):
                    before = self.position
                    self._write(v)
                    if k + 1 < len(steps):
                        self._pause(d.step_pause)
                        if self._set_invalid():     # the IOC did not confirm it: the actuator
                            raise End(ACTUATOR,     # is lost, nothing more is written
                                      "the set PV %s INVALID after the write of %g (the IOC "
                                      "did not confirm it); the last write before it %g"
                                      % (d.set_pv, v, before))
                reached = self._reach(target)
                if not reached:
                    notes.append("the read-back did not come within %g of %g in %g s"
                                 % (d.tolerance, target, d.settle_timeout))
            except End as exc:
                notes.append("end move stopped: %s" % exc.detail)
            except Exception:
                notes.append("end move failed: %s" % traceback.format_exc())
        with self.lock:
            rb = self.latest.get(d.readback_pv)
            set_r = self.latest.get(d.set_pv)
        end_wall = self.wall()
        self.meta.update({
            "state": "completed" if end.code == COMPLETED else "ended",
            "end_time": iso(end_wall),
            "duration_s": round(self.clock() - self.t_start, 3),
            "outcome": {"code": end.code, "reason": REASONS.get(end.code, "?"),
                        "detail": end.detail, "point": point, "phase": phase},
            "actuator_left": {
                "end": d.end, "target": target,
                "last_written": self.position,
                "set_pv_reads": None if problem(set_r) else float(set_r.value),
                "readback": None if problem(rb) else float(rb.value),
                "readback_problem": problem(rb),
                "readback_reached_target": reached,
                "writes_in_end_move": len(self.writes) - writes_before,
                "notes": notes,
            },
            "rows": self.files.rows,
            "writes": [[iso(t), v, p] for t, v, p in self.writes],
        })
        self.files.meta(self.meta)
        self.files.close()
        (log.info if end.code == COMPLETED else log.warning)(
            "scan ended: %s (%s), exit code %d; actuator left at %s, read-back %s; %s",
            REASONS.get(end.code), end.detail.strip().splitlines()[-1] if end.detail else "",
            end.code, self.position, self.meta["actuator_left"]["readback"],
            "; ".join(n.splitlines()[-1] for n in notes) or "-")

    def _set_invalid(self):
        with self.lock:
            r = self.latest.get(self.d.set_pv)
        return r is not None and r.severity is not None and r.severity >= INVALID

    def _pause(self, seconds):
        """A wait of the end move: nothing ends it."""
        end = self.clock() + seconds
        while self.clock() < end:
            self.sleep(min(self.tick, max(0.0, end - self.clock())))

    def _reach(self, target):
        t0 = self.clock()
        while True:
            with self.lock:
                r = self.latest.get(self.d.readback_pv)
                up = self.connected.get(self.d.readback_pv)
            if up and not problem(r) and abs(float(r.value) - target) <= self.d.tolerance:
                return True
            if self.clock() - t0 >= self.d.settle_timeout:
                return False
            self.sleep(self.tick)

    def _meta(self, plan, start, command):
        d = self.d
        try:
            import epics                   # noqa: F401  only for its version, when it is there
            pyepics = epics.__version__
        except Exception:
            pyepics = None
        return {
            "program": "mist2scan", "version": VERSION, "python": platform.python_version(),
            "pyepics": pyepics, "host": socket.gethostname(),
            "command": command or sys.argv,
            "definition_file": os.path.abspath(d.source) if d.source else None,
            "definition": d.data,
            "EPICS_CA_ADDR_LIST": os.environ.get("EPICS_CA_ADDR_LIST"),
            "state": "running",
            "start_time": iso(start), "end_time": None, "duration_s": None,
            "outcome": None, "actuator_left": None,
            "limits": plan["limits"], "before": plan["before"], "end_target": plan["end_target"],
            "pvs": plan["pvs"], "warnings": plan["warnings"],
            "points_planned": len(plan["points"]), "estimate_s": plan["estimate_s"],
            "channels": [{"column": n, "pv": pv} for n, pv in self.channels],
            "rows": 0, "writes": [],
        }


def _info(info, absent):
    if absent:
        return {"connected": False}
    info = info or {}
    keys = ("units", "precision", "lower_ctrl_limit", "upper_ctrl_limit", "lower_disp_limit",
            "upper_disp_limit")
    out = {"connected": True}
    out.update({k: info.get(k) for k in keys if k in info})
    return out


def _short(s):
    if s.status == MISSING:
        return "missing (%s)" % s.reason
    return "%.6g +- %.2g (n %d%s)" % (s.mean, s.spread, s.n,
                                     "" if s.status == "ok" else ", " + s.status)
