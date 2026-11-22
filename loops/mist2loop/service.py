"""The Channel Access side of the service: monitors on the loop's records, writes, the cycle.

Every record a loop reads is subscribed once with a monitor (pyepics, auto_monitor) and read
from the cache; nothing is polled. Writes do not wait for completion: they are plain records.
"""
import logging
import threading
import time

import epics

from .loop import READS, WRITES, Loop

log = logging.getLogger("mist2loop")


class Records:
    """The records of one loop, by suffix."""

    def __init__(self, prefix, loop_ref):
        self.prefix = prefix
        self.loop_ref = loop_ref               # the Loop, for the actuator's and writer's monitors
        self.pvs = {}
        for suffix in sorted(set(READS) | set(WRITES)):
            monitor = suffix in READS
            callback = {"_act": self._act, "_write.OVAL": self._oval}.get(suffix)
            self.pvs[suffix] = epics.PV("%s:%s" % (prefix, suffix), form="time",
                                        auto_monitor=monitor, callback=callback)

    def _act(self, value=None, **kw):
        if value is not None:
            self.loop_ref().on_act(value)

    def _oval(self, value=None, **kw):
        if value is not None:
            self.loop_ref().on_oval(value)

    def connected(self):
        return all(pv.connected and (pv.value is not None or not pv.auto_monitor)
                   for pv in self.pvs.values())

    def value(self, suffix):
        return float(self.pvs[suffix].value)

    def severity(self, suffix):
        severity = self.pvs[suffix].severity
        return 3 if severity is None else severity

    def put(self, suffix, value):
        self.pvs[suffix].put(value, wait=False)


class Service:
    def __init__(self, config):
        self.period = float(config["period_s"])
        self.loops = []
        for entry in config["loops"]:
            holder = []
            records = Records(entry["prefix"], lambda h=holder: h[0])
            holder.append(Loop(entry["prefix"], records, self.period))
            self.loops.append(holder[0])
        self.stopping = threading.Event()

    def run(self):
        log.info("started: %s, period %g s", ", ".join(l.prefix for l in self.loops), self.period)
        next_run = time.monotonic()
        while not self.stopping.is_set():
            for loop in self.loops:
                try:
                    loop.cycle()
                except Exception:                 # one bad cycle must not end the service
                    log.exception("%s: cycle failed", loop.prefix)
            epics.ca.flush_io()
            next_run += self.period
            delay = next_run - time.monotonic()
            if delay < 0:                        # late: no catching up with a burst
                next_run = time.monotonic()
                delay = 0
            self.stopping.wait(delay)
        for loop in self.loops:
            loop.stop()
        epics.ca.flush_io()
        log.info("stopped")
