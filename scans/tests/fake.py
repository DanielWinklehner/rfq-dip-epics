"""A fake Channel Access side and a fake time for the scan's unit tests. No EPICS.

World holds the PVs (value, severity, connected, time stamp), a clock that only moves when the
scan sleeps, and a small physics run every 10 ms of that clock: the read-back follows the set
point (instantly or with a lag), detectors are functions of the world evaluated every `period`
seconds, scheduled actions run at their time. A PV that changes is delivered to the scan as a
monitor would be: only when the value or the severity changes.
"""
import math

from mist2scan.engine import Reading

DT = 0.01


class PV:
    def __init__(self, value, severity=0, connected=True, lo=None, hi=None, units=""):
        self.value, self.severity, self.connected = value, severity, connected
        self.lo, self.hi, self.units = lo, hi, units
        self.stamp = 0.0


class World:
    def __init__(self, set_pv="X:set", readback_pv="X:get", start=0.0, lag=None,
                 lo=-100.0, hi=100.0):
        self.t = 1000.0
        self.set_pv, self.readback_pv = set_pv, readback_pv
        self.pvs = {set_pv: PV(start, lo=lo, hi=hi, units="A"),
                    readback_pv: PV(start, units="A")}
        self.lag = lag               # None: the read-back follows at once; else time constant, s
        self.follow = True           # False: the read-back is stuck
        self.detectors = {}          # name -> (function(world) -> value, period)
        self.next_eval = {}
        self.actions = []            # (time, function(world)), run once
        self.writes = []             # (time, name, value)
        self.on_value = self.on_connection = None
        self.reads = 0
        self.read_hook = None

    # --- set-up --------------------------------------------------------------------------

    def add(self, name, value=0.0, **kw):
        self.pvs[name] = PV(value, **kw)

    def detector(self, name, fn, period=0.1, **kw):
        self.add(name, fn(self), **kw)
        self.detectors[name] = (fn, period)
        self.next_eval[name] = self.t + period

    def at(self, seconds, fn):
        """Run fn(world) that many seconds from now."""
        self.actions.append((self.t + seconds, fn))

    def when(self, test, fn):
        """Run fn(world) once, the first time test(world) is true."""
        self.actions.append((test, fn))

    # --- changing PVs as the IOC would ---------------------------------------------------

    def post(self, name, value=None, severity=None):
        pv = self.pvs[name]
        changed = False
        if value is not None and value != pv.value:
            pv.value, changed = value, True
        if severity is not None and severity != pv.severity:
            pv.severity, changed = severity, True
        if changed:
            pv.stamp = self.t
            if pv.connected and self.on_value:
                self.on_value(name, Reading(pv.value, pv.severity, pv.stamp))

    def disconnect(self, name):
        pv = self.pvs[name]
        pv.connected = False
        if self.on_connection:
            self.on_connection(name, False)

    def reconnect(self, name):
        pv = self.pvs[name]
        pv.connected = True
        if self.on_connection:
            self.on_connection(name, True)
            self.on_value(name, Reading(pv.value, pv.severity, pv.stamp))

    # --- time ----------------------------------------------------------------------------

    def clock(self):
        return self.t

    def wall(self):
        return 1.7e9 + self.t

    def sleep(self, seconds):
        end = self.t + seconds
        while self.t < end:
            self.t = min(end, self.t + DT)
            self.physics()

    def physics(self):
        for item in list(self.actions):        # first: an action "when the set changes" acts
            cond, fn = item                    # before the read-back follows
            if (callable(cond) and cond(self)) or (not callable(cond) and self.t >= cond):
                self.actions.remove(item)
                fn(self)
        sp, rb = self.pvs[self.set_pv], self.pvs[self.readback_pv]
        if self.follow and rb.connected:
            if self.lag is None:
                target = sp.value
            else:
                target = rb.value + (sp.value - rb.value) * (1.0 - math.exp(-DT / self.lag))
                if abs(target - sp.value) < 1e-9:
                    target = sp.value
            self.post(self.readback_pv, target)
        for name, (fn, period) in self.detectors.items():
            if self.t >= self.next_eval[name] - 1e-9:
                self.next_eval[name] += period
                if self.pvs[name].connected:
                    self.post(name, fn(self))

    # --- what a scan sees: the io interface of ca.Channels -------------------------------

    def open(self, names, on_value, on_connection):
        self.on_value, self.on_connection = on_value, on_connection
        for n in names:
            pv = self.pvs.get(n)
            if pv is not None and pv.connected:
                on_connection(n, True)
                on_value(n, Reading(pv.value, pv.severity, pv.stamp))

    def wait_connected(self, names, timeout):
        return [n for n in names if n not in self.pvs or not self.pvs[n].connected]

    def read(self, name):
        self.reads += 1
        if self.read_hook:
            self.read_hook(self, name)
        pv = self.pvs.get(name)
        if pv is None or not pv.connected:
            return None
        return Reading(pv.value, pv.severity, pv.stamp)

    def info(self, name):
        pv = self.pvs[name]
        out = {"units": pv.units, "precision": 3}
        if pv.lo is not None:
            out.update(lower_ctrl_limit=pv.lo, upper_ctrl_limit=pv.hi)
        return out

    def write(self, name, value):
        assert name == self.set_pv, "a write to %s" % name
        pv = self.pvs[name]
        if pv.lo is not None and pv.hi > pv.lo:
            assert pv.lo <= value <= pv.hi, "%g outside the control limits" % value
        if not pv.connected:
            return False
        self.writes.append((self.t, name, value))
        self.post(name, value)
        return True

    def close(self):
        pass

    # --- for the assertions --------------------------------------------------------------

    def written(self, after=None):
        return [v for t, _, v in self.writes if after is None or t > after]
