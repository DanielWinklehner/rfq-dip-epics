"""One loop: its mode, its checks, the hand-back and the refusal. No EPICS import.

The loop knows only its prefix. Every name below is a record of EPICS/Db/loop.db, loaded with
that prefix; the names of the measurement, the actuator and the permit conditions are written
once, in the load line of that file. `io` is the service's Channel Access side (service.py): its
records are kept current by monitors, the loop reads them from there and writes with io.put.
"""
import logging
import threading
import time

from . import pid

INVALID = 3

# The states of <prefix>:reason:get, in this order (loop.db).
REASONS = ["none", "IOC start", "service start", "permit 1", "permit 2", "permit 3",
           "permit 1 no data", "permit 2 no data", "permit 3 no data", "measurement no data",
           "actuator no data", "measurement stale", "written by someone else",
           "set not accepted", "outside output limits", "service stopped"]
(NONE, IOC_START, SERVICE_START, PERMIT1, _, _, NODATA1, _, _, MEASUREMENT, ACTUATOR, STALE,
 OVERRIDDEN, NOT_ACCEPTED, RANGE, SERVICE_STOPPED) = range(len(REASONS))

# What the loop reads (monitors) and writes.
READS = ["mode:setpoint", "_active", "permit1:get", "permit2:get", "permit3:get", "value:read",
         "_act", "_hb", "_write.OVAL", "value:setpoint", "value:setpoint.DRVL",
         "value:setpoint.DRVH", "kp:setpoint", "ki:setpoint", "kd:setpoint", "dfilter:setpoint",
         "outmin:setpoint", "outmax:setpoint", "slew:setpoint", "stale:setpoint", "_count"]
WRITES = ["_count", "_out", "_active", "mode:setpoint", "reason:get", "output:get", "error:get",
          "p:get", "i:get", "d:get", "limit:get"]

DT_MAX_PERIODS = 3.0    # a gap longer than three periods is integrated as three


def same(a, b):
    return abs(a - b) <= 1e-9 * (abs(a) + abs(b) + 1.0)


class Loop:
    def __init__(self, prefix, io, period, clock=time.monotonic):
        self.prefix = prefix
        self.io = io
        self.period = period
        self.clock = clock
        self.log = logging.getLogger("mist2loop.%s" % prefix)
        self.lock = threading.Lock()
        self.pid = False             # mode as this service sees it
        self.started = False         # first contact with the records done
        self.connected = False
        self.count = None
        self.last_run = None
        self.hb = None               # heartbeat value seen last, and when it changed
        self.hb_time = None
        self.oval = None             # the last value the IOC's writer sent to the actuator
        self.overridden = False      # the actuator changed to a value the writer did not send
        self.state = None
        self.result = None

    # --- called from the monitors (Channel Access threads) ----------------------------------

    def on_oval(self, value):
        with self.lock:
            self.oval = value

    def on_act(self, value):
        """A new value of the actuator's set point. In PID it must be what the writer sent (the
        writer's monitor comes first on the same circuit); anything else is someone else's."""
        with self.lock:
            if self.pid and self.oval is not None and not same(value, self.oval):
                self.overridden = True

    # --- once per period ---------------------------------------------------------------------

    def v(self, suffix):
        return self.io.value(suffix)

    def bad(self, suffix):
        return self.io.severity(suffix) >= INVALID

    def params(self):
        return pid.Params(kp=self.v("kp:setpoint"), ki=self.v("ki:setpoint"),
                          kd=self.v("kd:setpoint"), tf=self.v("dfilter:setpoint"),
                          out_min=self.v("outmin:setpoint"), out_max=self.v("outmax:setpoint"),
                          slew=self.v("slew:setpoint"), dt_max=DT_MAX_PERIODS * self.period)

    def set_point(self):
        sp, lo, hi = (self.v(s) for s in ("value:setpoint", "value:setpoint.DRVL",
                                           "value:setpoint.DRVH"))
        return min(max(sp, lo), hi) if hi > lo else sp

    def check(self, in_pid, now):
        """The first condition that is not fulfilled, or NONE."""
        if self.bad("value:read"):
            return MEASUREMENT
        if self.bad("_act"):
            return NOT_ACCEPTED if in_pid else ACTUATOR
        permits = [self.v("permit%d:get" % n) for n in (1, 2, 3)]
        for n, state in enumerate(permits):
            if state > 1.5:
                return NODATA1 + n
        for n, state in enumerate(permits):
            if state > 0.5:
                return PERMIT1 + n
        if self.hb_time is None or now - self.hb_time > self.v("stale:setpoint"):
            return STALE
        if in_pid and self.overridden:
            return OVERRIDDEN
        act, lo, hi = self.v("_act"), self.v("outmin:setpoint"), self.v("outmax:setpoint")
        if not in_pid and not (lo < hi and lo <= act <= hi):
            return RANGE
        return NONE

    def go_manual(self, reason, request_off):
        self.io.put("_active", 0)
        if request_off:
            self.io.put("mode:setpoint", 0)
        self.io.put("reason:get", reason)
        with self.lock:
            self.pid = False
        self.log.info("MANUAL: %s", REASONS[reason] if reason else "requested")

    def cycle(self):
        now = self.clock()
        if not self.io.connected():
            if self.connected:
                self.log.warning("records not connected: MANUAL")
            self.connected = False
            with self.lock:
                self.pid = False
            return
        if not self.connected:
            self.connected = True
            self.log.info("records connected")
            self.last_run = None
            self.count = int(self.v("_count"))
            if not self.started:            # a start of the service: MANUAL, whatever was on
                self.started = True
                self.go_manual(SERVICE_START, True)
            elif self.v("_active"):         # reconnected (an IOC start): nothing goes on
                self.io.put("_active", 0)
        dt = 0.0 if self.last_run is None else now - self.last_run
        self.last_run = now
        self.count = (self.count + 1) % 2 ** 31
        self.io.put("_count", self.count)

        hb = self.v("_hb")
        if hb != self.hb:
            if self.hb is not None:
                self.hb_time = now
            self.hb = hb
        request = self.v("mode:setpoint") > 0.5
        sp, pv, act = self.set_point(), self.v("value:read"), self.v("_act")
        p = self.params()

        if not self.pid:
            if request:
                why = self.check(False, now)
                if why:
                    self.io.put("mode:setpoint", 0)
                    self.io.put("reason:get", why)
                    self.log.info("PID refused: %s", REASONS[why])
                else:
                    self.state, self.result = pid.start(p, sp, pv, act)
                    with self.lock:
                        self.overridden = False
                        self.pid = True
                    self.io.put("_out", act)            # the writer's target first
                    self.io.put("reason:get", NONE)
                    self.io.put("_active", 1)
                    self.log.info("PID from %g", act)
        elif not request:
            self.go_manual(NONE, False)
        else:
            why = self.check(True, now)
            if why:
                self.go_manual(why, True)               # the actuator keeps its set point
            else:
                self.state, self.result = pid.step(self.state, p, sp, pv, dt)
                self.io.put("_out", self.result.out)

        if self.pid:
            r = self.result
            shown = (r.out, r.error, r.p, r.i, r.d, r.limited)
        else:                                           # MANUAL: follow the actuator
            self.io.put("_out", act)
            shown = (act, sp - pv, 0.0, 0.0, 0.0, pid.FREE)
        for suffix, value in zip(("output:get", "error:get", "p:get", "i:get", "d:get",
                                  "limit:get"), shown):
            self.io.put(suffix, value)

    def stop(self):
        """SIGTERM: leave the loop in MANUAL."""
        if self.connected and (self.pid or self.v("mode:setpoint") > 0.5):
            self.go_manual(SERVICE_STOPPED, True)
