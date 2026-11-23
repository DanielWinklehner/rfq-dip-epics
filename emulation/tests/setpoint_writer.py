"""A client that writes a Matsusada supply's voltage set point in a tight loop while its IOC
restarts (P40, EPICS/Db/supply_first_contact.db). Used by test_11_first_contact.py (an AU supply,
rack IOC) and test_09_loop.py (the REK, platform IOC), on restarts those modules do anyway.

The invariant the old records (a seq between the copy of the echo and the end of simulation mode)
could break and the new ones cannot: whenever the set point is out of simulation mode and no
write of this client is in flight, the set point shows the voltage the supply has. The writer
checks it before and after every write (SIMM read first; then the record and the simulator's
own setting), and once more at the end, when it has stopped: SIMM NO, set point = echo =
simulator. A write in the old gap (processed in simulation mode after the copy, so neither sent
nor replaced) leaves the set point at the client's value while the supply keeps its own: seen at
the next check with SIMM NO. A write the IOC confirmed with SIMM NO and without alarm is thereby
received by the simulator (the set point and the simulator agree right after it) or was replaced
by the take-over (the record shows the supply's value)."""
import threading
import time

import epics

import system as S
from system import reg


class SetpointWriter:
    """with SetpointWriter(device) as w: w.silence(); <restart the IOC>; w.answer_after_writes();
    w.wait_taken_over(); ... then w.stop() (also done on exit) and w.problems() / w.summary().

    The supply is held silent through the IOC's start (fault "silent" on its unit) and answers
    only after the client has written into simulation mode: a supply that answers at once is
    taken over within some 0.1 s of iocInit, before a Channel Access client has reconnected, so
    the take-over would never meet a write."""

    def __init__(self, device, values=None):
        self.device = device
        self.req = reg.role(device, "vset")
        self.echo = reg.role(device, "vget")
        self.sim, self.unit = reg.sim_of(self.req)
        self.signal = "%d.vset" % self.unit
        lo, hi = reg.pvs[self.req]["test"]
        self.values = values or (lo + 0.4 * (hi - lo), lo + 0.6 * (hi - lo))
        full = max(abs(float(S.field(self.req, "DRVH"))), abs(float(S.field(self.req, "DRVL"))))
        self.tol = 1.5 * full / 0xFFFF                 # 16-bit set (CH0), echo and simulator
        self.found = S.get(self.req)
        self.writes = []         # (value, severity, SIMM after) of each put that returned 1
        self.failed = 0          # puts that raised or did not complete (IOC away)
        self.bad = []            # observations that break the invariant
        self.checked = 0
        self._stop = threading.Event()
        self._thread = None
        self._stopped = False
        self._silent = False

    # --- the writer ---------------------------------------------------------------------------

    def _check(self, pv, simm, ctl, when, value):
        """SIMM NO and nothing in flight: the set point equals the simulator's setting."""
        if simm.get(use_monitor=False, timeout=1.0, as_string=True) != "NO":
            return
        d = pv.get_with_metadata(use_monitor=False, form="time", timeout=1.0)
        if d is None or d["severity"] == S.INVALID:
            return
        supply = ctl.get(self.signal)["value"]
        self.checked += 1
        if abs(abs(d["value"]) - supply) > self.tol:
            self.bad.append((when, value, d["value"], supply))

    def _run(self):
        from mist2sim.control import ControlClient
        host, port = reg.simulators[self.sim]["host"], reg.simulators[self.sim]["control_port"]
        pv = epics.PV(self.req, form="time", auto_monitor=False)
        simm = epics.PV(self.req + ".SIMM", auto_monitor=False)
        ctl = ControlClient(host, port, timeout=5.0)
        i = 0
        while not self._stop.is_set():
            if not (pv.connected and simm.connected):
                time.sleep(0.005)
                continue
            value = self.values[i % 2]
            try:
                self._check(pv, simm, ctl, "before", value)
                ok = pv.put(value, wait=True, timeout=2.0)
                if ok != 1:
                    self.failed += 1
                    continue
                after = simm.get(use_monitor=False, timeout=1.0, as_string=True)
                d = pv.get_with_metadata(use_monitor=False, form="time", timeout=1.0)
                if d is not None:
                    self.writes.append((value, d["severity"], after))
                self._check(pv, simm, ctl, "after", value)
                i += 1
            except Exception:                         # noqa: BLE001  the IOC goes away
                self.failed += 1
                time.sleep(0.01)
        ctl.close()

    def __enter__(self):
        self._thread = epics.ca.CAThread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def silence(self):
        """The supply's unit silent (before the IOC restarts)."""
        S.control(self.sim).fault("silent", unit=self.unit)
        self._silent = True

    def answer(self):
        if self._silent:
            S.control(self.sim).clear("silent", unit=self.unit)
            self._silent = False

    def in_simm(self):
        return sum(1 for w in list(self.writes) if w[2] != "NO")

    def answer_after_writes(self, count=20, timeout=20.0):
        """The IOC is back: wait until `count` more writes went into simulation mode, then let
        the supply answer while the writes go on."""
        start = self.in_simm()
        try:
            S.wait_for(lambda: self.in_simm() >= start + count, timeout,
                       lambda: "%d writes into simulation mode (%d so far)" % (count, self.in_simm() - start))
        finally:
            self.answer()

    def wait_taken_over(self, timeout):
        """The IOC is back and the set point has taken over (SIMM NO), then one more second of
        writes after it."""
        S.wait_for(lambda: S.connected(self.req) and S.field(self.req, "SIMM") == "NO", timeout,
                   lambda: "%s out of simulation mode: SIMM %s" % (self.req, S.field(self.req, "SIMM")))
        time.sleep(1.0)

    def stop(self, restore=True):
        """Stops the writer; the final state is checked, then the set point found is written
        back."""
        if self._stopped:
            return
        self._stopped = True
        self._stop.set()
        self._thread.join(10)
        self.answer()
        since = time.time()
        S.put_field(self.echo, "PROC", 1)              # a fresh echo, read after the last write
        S.wait_fresh(self.echo, since, lambda v: True, 5.0, "echo after the writes")
        self.final = dict(simm=S.field(self.req, "SIMM"), setpoint=S.get(self.req), severity=S.sevr(self.req),
                          echo=S.get(self.echo), supply=S.sim_value(self.sim, self.signal))
        if restore:
            S.put(self.req, self.found)

    # --- results ------------------------------------------------------------------------------

    def problems(self):
        out = []
        f = self.final
        if f["simm"] != "NO":
            out.append("SIMM %s at the end" % f["simm"])
        if f["severity"] == S.INVALID:
            out.append("set point INVALID at the end")
        if abs(f["setpoint"] - f["echo"]) > self.tol or abs(abs(f["setpoint"]) - f["supply"]) > self.tol:
            out.append("at the end set point %r, echo %r, simulator %r" % (f["setpoint"], f["echo"], f["supply"]))
        if self.bad:
            out.append("%d checks with SIMM NO where the set point did not show the supply's setting "
                       "(when, written, set point, simulator): %s" % (len(self.bad), self.bad[:5]))
        if not any(w[2] == "NO" and w[1] != S.INVALID for w in self.writes):
            out.append("no write confirmed without alarm after the take-over")
        return out

    def summary(self):
        in_simm = sum(1 for w in self.writes if w[2] != "NO")
        return ("%s through the IOC restart: %d writes confirmed (%d of them in simulation mode, before the "
                "take-over; %d in alarm), %d not completed while the IOC was away, %d checks of set point = "
                "supply" % (self.req, len(self.writes), in_simm, sum(1 for w in self.writes if w[1] == S.INVALID),
                            self.failed, self.checked))
