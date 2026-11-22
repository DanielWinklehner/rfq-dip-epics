"""The logger service: Channel Access monitors in, batches to the database, its state to the rack IOC.

Threads: Channel Access calls back from its own thread; the callbacks only queue what arrived.
The main thread turns it into rows once a second (core.Recorder) and hands the batch to the
writer thread (store.Store). SIGTERM (docker stop, systemctl stop) writes what is left and a stop
event.
"""
import collections
import logging
import math
import signal
import threading
import time

import epics

from . import core
from .config import Settings, load_registry
from .store import Store

log = logging.getLogger("mist2log")
TICK = 1.0     # seconds: one batch, one write of the state records


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.inbox = collections.deque()      # filled by the Channel Access thread
        self.stop = threading.Event()

    def run(self):
        s = self.settings
        channels, tiers = load_registry(s.registry)
        self.store = Store(s, tiers)
        ids, through, known, alive = self.store.open(channels)
        chans = []
        for ch in channels:
            c = core.Channel(ids[ch.name], ch.name, ch.tier, ch.kind, ch.written, ch.states,
                             ids.get(ch.context) if ch.context else None)
            chans.append(c)
        self.recorder = rec = core.Recorder(chans, s.clock_skew, s.close_delay)
        now = time.time()
        rec.start(through, known, now)
        rec.batch.started = now
        rec.batch.events.append((now, None, "logger", None, "start", None, None, None,
                                 "%d PVs; data before %s" % (len(chans), "none" if through is None else
                                 "complete up to %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(through[0])))))
        self.store.start()
        log.info("logging %d PVs (%s)", len(chans), ", ".join(
            "%s %d" % (t, sum(1 for c in chans if c.tier == t)) for t in ("raw", "seconds", "minutes", "events")))

        by_id = {c.id: c for c in chans}
        self.pvs = []
        for ch in channels:
            c = by_id[ids[ch.name]]
            self.pvs.append(epics.PV(ch.ca_name, form="time", auto_monitor=True,
                                     callback=self._monitor, connection_callback=self._connection,
                                     connection_timeout=2.0))
            self.pvs[-1].mist2 = c
        self.names = {pv.pvname: pv.mist2 for pv in self.pvs}
        status = {key: epics.PV("%s:%s:get" % (s.status_prefix, key), connection_timeout=2.0)
                  for key in ("count", "connected", "disconnected", "rows", "db", "buffer", "dropped")}

        signal.signal(signal.SIGTERM, lambda *a: self.stop.set())
        signal.signal(signal.SIGINT, lambda *a: self.stop.set())
        count = 0
        next_tick = time.time() + TICK
        while not self.stop.wait(max(0.0, next_tick - time.time())):
            next_tick += TICK
            now = time.time()
            self._drain(now)
            self.store.put(rec.tick(now))
            lost = self.store.take_loss()
            if lost:
                through_kept, first, rows = lost
                b = rec.resume(through_kept or (first, math.floor(first), math.floor(first / 60) * 60), now)
                b.events.append((first, None, "logger", None, "rows lost", rows, None, None,
                                 "%d rows did not fit into the buffer from %s to %s" % (
                                     rows, time.strftime("%H:%M:%S", time.localtime(first)),
                                     time.strftime("%H:%M:%S", time.localtime(now)))))
                self.store.put(b, force=True)
            count += 1
            st = self.store.status()
            up = sum(1 for c in chans if c.connected)
            for key, value in (("count", count), ("connected", up), ("disconnected", len(chans) - up),
                               ("rows", st["rows"]), ("db", 1 if st["db"] else 2), ("buffer", st["buffer"]),
                               ("dropped", st["dropped"])):
                if status[key].connected:
                    status[key].put(value, wait=False)
        now = time.time()
        self._drain(now)
        b = rec.tick(now)
        b.events.append((now, None, "logger", None, "stop", None, None, None, None))
        self.store.put(b, force=True)
        self.store.close()
        log.info("stopped")

    # --- Channel Access thread: queue only ----------------------------------------------------
    def _monitor(self, pvname=None, value=None, severity=None, status=None, timestamp=None, **kw):
        self.inbox.append(("u", pvname, value, severity, status, timestamp))

    def _connection(self, pvname=None, conn=None, **kw):
        if not conn:
            self.inbox.append(("d", pvname))

    # --- main thread --------------------------------------------------------------------------
    def _drain(self, now):
        rec = self.recorder
        while self.inbox:
            item = self.inbox.popleft()
            ch = self.names.get(item[1])
            if ch is None:
                continue
            if item[0] == "d":
                rec.disconnect(ch, now)
                continue
            _, _, value, severity, status, stamp = item
            text = None
            if ch.kind == "enum":
                value = int(value)
                text = ch.states[value] if 0 <= value < len(ch.states) else None
            elif ch.kind == "text":
                text = value if isinstance(value, str) else bytes(bytearray(value)).split(b"\0")[0].decode(errors="replace")
                value = None
            else:
                value = float(value)
            rec.update(ch, value, text, severity, status, stamp if stamp is not None else now, now)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Service(Settings()).run()
