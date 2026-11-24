"""The dipole scan with its three parts together (task T27): the shipped scan program
(scans/mist2scan) runs the shipped definition (scans/config/dipole.yaml) through one IOC
(dipole.db, picoammeter.db) against the DAQ service (daq/mist2daq, sim backend) and the Keithley
6485 simulator, coupled by coupling.py (a spectrum of three peaks over the magnet current; a model
of this case, coupling.yaml).

    emulation/devtest/run.sh emulation/devtest/dipolescan

Only the command line's overrides (--start, --stop, --step, --dwell, --output) change the run;
where a test needs anything else of the definition it says so (a finding, not a second
definition). The service's status port (6000) gives what the IOC cannot: what the service holds
and wrote, and which commands reached it. The tests run in the order of this file and build on
each other: the first needs the parts as they start (service just started, picoammeter at power-on).
"""
import csv
import glob
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

import epics
import numpy
import pytest
import yaml

from mist2sim.control import ControlClient

SIM = os.environ["SIM_HOST"]
BUILD = os.environ["DEVTEST_BUILD"]
CASE = os.path.dirname(os.path.abspath(__file__))
SCANS = "/repo/scans"
DEFINITION = os.path.join(SCANS, "config", "dipole.yaml")       # the shipped definition
SET, HELD, RB = "dipole:current:set", "dipole:current:held", "dipole:current:get"
PICO = "pico1:current:get"
INVALID = 3

with open(DEFINITION) as _h:
    SHIPPED = yaml.safe_load(_h)
with open(os.path.join(CASE, "coupling.yaml")) as _h:
    COUPLING = yaml.safe_load(_h)
with open(os.path.join(CASE, "sim.yaml")) as _h:
    NOISE = float(yaml.safe_load(_h)[0]["options"]["noise"])
TOL = SHIPPED["actuator"]["tolerance"]
MAX_STEP = SHIPPED["actuator"]["max_step"]
PEAKS = [COUPLING["first_peak_a"] * math.sqrt(p["mass"]) for p in COUPLING["peaks"]]
PARK = 6.0                      # A: where the tests leave the magnet before a scan (end: previous)


def spectrum(x):
    """The coupling's model (coupling.py), evaluated here independently of it."""
    y = COUPLING["background_a"]
    for p, x0 in zip(COUPLING["peaks"], PEAKS):
        y += p["height_a"] * math.exp(-0.5 * ((x - x0) / p["sigma_a"]) ** 2)
    return y


# --- helpers ------------------------------------------------------------------------------------

def status():
    """The DAQ service's status port: what it holds, wrote and received."""
    with socket.create_connection((SIM, 6000), timeout=3) as s:
        s.sendall(b'{"cmd": "status"}\n')
        line = s.makefile().readline()
    reply = json.loads(line)
    assert reply["ok"], reply
    return reply["status"]


def sets_received(st=None):
    c = (st or status())["counts"]["commands"]
    return c.get("S", 0) + c.get("s", 0)


def service(state):
    """Stop ("stop") or start ("run") the DAQ service (run_service.sh of the dipole case)."""
    with open(os.path.join(BUILD, "daq-run"), "w") as f:
        f.write(state + "\n")


def restart_ioc():
    path = os.path.join(BUILD, "ioc-restart")
    with open(path) as f:
        n = len(f.read())
    with open(path, "w") as f:
        f.write("x" * (n + 1))


def read(name):
    d = epics.PV(name, auto_monitor=False).get_with_metadata(use_monitor=False, form="time",
                                                             timeout=3)
    assert d is not None, "%s does not answer" % name
    return d


def put(name, value):
    assert epics.caput(name, value, wait=True, timeout=10) == 1, "caput %s" % name


def wait_until(test, timeout, what):
    end = time.monotonic() + timeout
    while True:
        last = test()
        if last:
            return last
        if time.monotonic() > end:
            pytest.fail("no %s within %g s" % (what, timeout))
        time.sleep(0.05)


def valid(name):
    """Connected, not INVALID, a finite number (False while it does not answer)."""
    d = epics.PV(name, auto_monitor=False).get_with_metadata(use_monitor=False, form="time",
                                                             timeout=3)
    return d is not None and d["severity"] < INVALID and math.isfinite(d["value"])


class Watch:
    """Every value of a PV as a monitor delivers it: (monotonic time, value); a disconnect as
    (time, None)."""

    def __init__(self, name):
        self.events = []
        self.lock = threading.Lock()
        self.pv = epics.PV(name, auto_monitor=True, callback=self._cb,
                           connection_callback=self._conn)
        assert self.pv.wait_for_connection(5.0)
        end = time.monotonic() + 5.0
        while not self.events and time.monotonic() < end:
            time.sleep(0.01)
        assert self.events, "no first value of %s" % name

    def _cb(self, value=None, **kw):
        with self.lock:
            self.events.append((time.monotonic(), float(value)))

    def _conn(self, conn=None, **kw):
        if not conn:
            with self.lock:
                self.events.append((time.monotonic(), None))

    def since(self, t):
        with self.lock:
            return [v for tt, v in self.events if tt > t]

    def last(self):
        with self.lock:
            return self.events[-1][1] if self.events else None

    def close(self):
        self.pv.clear_callbacks(with_connect_callback=True)
        self.pv.disconnect()


class Run:
    """python -m mist2scan <command> <definition> [overrides], as the owner runs it; its output
    in build/<name>.log, its files in build/out/<name>."""

    def __init__(self, name, *args, command="run", definition=DEFINITION):
        self.out = os.path.join(BUILD, "out", name)
        shutil.rmtree(self.out, ignore_errors=True)
        self.log = os.path.join(BUILD, name + ".log")
        self.handle = open(self.log, "w")
        self.t0 = time.monotonic()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mist2scan", command, definition, "--output", self.out]
            + [str(a) for a in args],
            env=dict(os.environ, PYTHONPATH=SCANS), cwd=SCANS, stdout=self.handle,
            stderr=subprocess.STDOUT)

    def wait(self, timeout=300):
        try:
            code = self.proc.wait(timeout)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            self.handle.close()
        self.seconds = time.monotonic() - self.t0
        return code

    def text(self):
        with open(self.log) as handle:
            return handle.read()

    def directory(self):
        dirs = glob.glob(os.path.join(self.out, "*"))
        assert len(dirs) == 1, dirs
        return dirs[0]

    def rows(self):
        with open(os.path.join(self.directory(), "points.csv")) as handle:
            return list(csv.DictReader(handle))

    def meta(self):
        with open(os.path.join(self.directory(), "scan.json")) as handle:
            return json.load(handle)


def changed_definition(name, change):
    """A copy of the shipped definition with one change, in build/defs (a finding of the test
    that uses it, not a definition of this case)."""
    data = yaml.safe_load(open(DEFINITION))
    change(data)
    os.makedirs(os.path.join(BUILD, "defs"), exist_ok=True)
    path = os.path.join(BUILD, "defs", name + ".yaml")
    with open(path, "w") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return path


def park(value=PARK):
    """The operator's set of the magnet before a scan; waits for the read-back."""
    put(SET, value)
    wait_until(lambda: valid(RB) and abs(read(RB)["value"] - value) <= TOL / 5, 20,
               "read-back at %g" % value)


def assert_back_in_part_steps(values, start, end):
    assert values, "no write after the cause"
    assert values[-1] == pytest.approx(end)
    prev = start
    for v in values:
        assert abs(v - prev) <= MAX_STEP + 1e-6, values
        assert abs(v - end) < abs(prev - end) + 1e-9, values
        prev = v


def log_since(name, mark):
    with open(os.path.join(BUILD, name)) as handle:
        return handle.read()[mark:]


def log_mark(name):
    return os.path.getsize(os.path.join(BUILD, name))


def table(run):
    return numpy.genfromtxt(os.path.join(run.directory(), "points.csv"), delimiter=",",
                            names=True, dtype=None, encoding="utf-8")


# --- 0: the parts are there ------------------------------------------------------------------------

def test_every_part_connects():
    for name in (SET, HELD, RB, PICO, "pico1:zcheck:set", "pico1:range:set", "dipole:id"):
        assert epics.PV(name).wait_for_connection(5), name
    wait_until(lambda: valid(RB) and valid("pico1:zcheck:get"), 40, "service and picoammeter read")
    with ControlClient(SIM, 6001) as c:
        x = c.get("current")
    assert x["external"] is True, x                    # the coupling holds the input
    assert x["value"] == pytest.approx(spectrum(0.0), rel=1e-6)   # magnet at 0 A after the start


# --- 1: after power-on the scan refuses ------------------------------------------------------------

def test_1_after_power_on_the_scan_refuses_and_writes_nothing():
    st = status()
    assert st["channels"]["o1"]["held"] is None and sets_received(st) == 0, st
    assert read(SET)["severity"] == INVALID              # the service holds nothing yet
    assert read("pico1:zcheck:get")["value"] == 1        # power-on: zero check ON
    assert read(PICO)["severity"] == INVALID

    c = Run("refused-check", command="check")
    assert c.wait(60) == 3, c.text()
    assert "actuator set PV dipole:current:set: INVALID" in c.text()
    assert "detector pico1 (pico1:current:get): INVALID" in c.text()
    r = Run("refused-run")
    assert r.wait(60) == 3, r.text()
    assert "refused, nothing written" in r.text()
    assert "actuator set PV dipole:current:set: INVALID" in r.text()
    assert "detector pico1 (pico1:current:get): INVALID" in r.text()
    assert not os.path.exists(r.out)
    st = status()
    assert (sets_received(st), st["sim"]["writes"]) == (0, 0), st

    # The operator sets the magnet once (the service's held value becomes known); the
    # picoammeter still refuses the scan.
    park()
    n = sets_received()
    r = Run("refused-zcheck")
    assert r.wait(60) == 3, r.text()
    assert "detector pico1 (pico1:current:get): INVALID" in r.text()
    assert "actuator" not in r.text().split("refused, nothing written")[1]
    assert sets_received() == n

    # Zero check off through its PV: the scan would start.
    put("pico1:zcheck:set", 0)
    wait_until(lambda: valid(PICO), 10, "a valid picoammeter reading")
    c = Run("start-check", command="check")
    assert c.wait(60) == 0, c.text()
    assert "it would start" in c.text()
    assert sets_received() == n


# --- 2: the spectrum ---------------------------------------------------------------------------------

def find_peaks(x, y):
    """Local maxima well above the background; the vertex of the parabola through the
    logarithms of the three points around each (exact for a Gaussian)."""
    bg = COUPLING["background_a"]
    out = []
    for k in range(1, len(y) - 1):
        if y[k] > y[k - 1] and y[k] >= y[k + 1] and y[k] - bg > 20 * NOISE:
            l0, l1, l2 = (math.log(max(v - bg, NOISE)) for v in y[k - 1:k + 2])
            h = x[k + 1] - x[k]
            out.append((x[k] + h * (l0 - l2) / (2 * (l0 - 2 * l1 + l2)), k))
    return out


RESULTS = {}


def test_2_the_spectrum():
    park()
    step = 0.5
    r = Run("spectrum", "--start", 7.0, "--stop", 19.5, "--step", step)
    assert r.wait() == 0, r.text()
    rows = r.rows()
    assert len(rows) == 26
    assert {x["outcome"] for x in rows} == {"ok"}
    for x in rows:
        assert abs(float(x["readback_mean"]) - float(x["set"])) <= TOL
        assert x["pico1_status"] == "ok"
    t = table(r)
    x, y = t["readback_mean"], t["pico1_mean"]
    found = find_peaks(x, y)
    print("peaks found at %s A, coupling %s A" % (["%.3f" % f for f, _ in found],
                                                 ["%.3f" % p for p in PEAKS]))
    assert len(found) == 3, list(zip(x, y))
    for (f, k), p, spec in zip(found, PEAKS, COUPLING["peaks"]):
        assert abs(f - p) <= step
        model = spectrum(x[k])
        print("peak %g: point %g A measured %.4g A, model %.4g A, difference %.2g A"
              % (p, x[k], y[k], model, y[k] - model))
        assert abs(y[k] - model) <= 5 * NOISE
    dev = [y[k] - spectrum(x[k]) for k in range(len(x))]
    print("every point, measured - model: max |d| %.3g A, rms %.3g A (noise %g A)"
          % (max(abs(d) for d in dev), math.sqrt(sum(d * d for d in dev) / len(dev)), NOISE))
    m = r.meta()
    assert (m["state"], m["outcome"]["code"], m["rows"]) == ("completed", 0, 26)
    assert m["actuator_left"]["readback_reached_target"] is True
    assert m["actuator_left"]["last_written"] == PARK
    assert status()["channels"]["o1"]["held"] == pytest.approx(PARK)
    # R4: values per point and time per point, as measured here
    n = [int(v) for v in t["pico1_n"]]
    el = list(t["elapsed_s"])
    per_point = [b - a for a, b in zip(el, el[1:])]
    RESULTS["spectrum"] = {"n": n, "per_point_s": per_point, "duration_s": m["duration_s"],
                           "estimate_s": m["estimate_s"]}
    print("R4 dwell %g s: pico1_n per point %s; readback_n %s; time per point %.2f to %.2f s, "
          "mean %.2f s; scan %.1f s, estimate of check %s"
          % (SHIPPED["dwell"], n, [int(v) for v in t["readback_n"]], min(per_point),
             max(per_point), sum(per_point) / len(per_point), m["duration_s"], m["estimate_s"]))


# --- R4: values per point against the dwell --------------------------------------------------------

@pytest.mark.parametrize("dwell", [3.0, 5.0])
def test_r4_values_per_point(dwell):
    """Three points on the background with a longer dwell: how many picoammeter values a point
    gets, and the time per point (printed for SCAN.md)."""
    park()
    r = Run("dwell%g" % dwell, "--start", 7.0, "--stop", 8.0, "--step", 0.5, "--dwell", dwell)
    assert r.wait() == 0, r.text()
    t = table(r)
    n = [int(v) for v in t["pico1_n"]]
    el = list(t["elapsed_s"])
    per_point = [b - a for a, b in zip(el, el[1:])]
    print("R4 dwell %g s: pico1_n %s, readback_n %s, time per point %s s"
          % (dwell, n, [int(v) for v in t["readback_n"]], ["%.2f" % x for x in per_point]))
    # one new reading per second (picoammeter.db SCAN 1 s) plus the fresh read at the start
    assert all(int(dwell) <= k <= int(dwell) + 2 for k in n), n


# --- 3: overflow at a peak ------------------------------------------------------------------------

RANGE_20NA, OVERFLOW_A = 2, 2e-8 * 1.05          # range:set state 2 = 20 nA; overflow above 105 %


def fixed_range(state):
    put("pico1:range:set", state)
    if state:
        wait_until(lambda: read("pico1:range:get")["value"] == state - 1, 10,
                   "range state %d" % state)          # range:get: 0 = 2 nA, 1 = 20 nA ...
    wait_until(lambda: read("pico1:_auto")["value"] == (0 if state else 1), 10, "autorange")


def test_3_overflow_at_a_peak():
    park()
    fixed_range(RANGE_20NA)
    points = numpy.arange(8.0, 16.01, 0.5)
    over = [x for x in points if spectrum(x) > OVERFLOW_A]
    assert over == [9.5, 10.0, 10.5]
    assert all(abs(spectrum(x) - OVERFLOW_A) > 20 * NOISE for x in points)   # no point near it
    try:
        # As shipped (the picoammeter required): the first point on the peak ends the scan.
        w = Watch(SET)
        try:
            r = Run("overflow-shipped", "--start", 8, "--stop", 16, "--step", 0.5)
            code = r.wait()
            after = w.since(w.events[0][0])
        finally:
            w.close()
        assert code == 6, r.text()
        rows = r.rows()
        assert [float(x["set"]) for x in rows] == [8.0, 8.5, 9.0, 9.5]
        assert [x["pico1_status"] for x in rows] == ["ok", "ok", "ok", "missing"]
        assert (rows[-1]["pico1_reason"], rows[-1]["pico1_n"]) == ("INVALID", "0")
        assert r.meta()["outcome"]["reason"] == "required detector lost"
        k = after.index(9.5)
        assert_back_in_part_steps(after[k + 1:], 9.5, PARK)
        assert status()["channels"]["o1"]["held"] == pytest.approx(PARK)

        # With the picoammeter optional (one key changed: a finding, see SCAN.md): the scan
        # completes, the points on the peak missing with their reason, the others measured.
        def optional(d):
            d["detectors"][0]["required"] = False
        r = Run("overflow", "--start", 8, "--stop", 16, "--step", 0.5,
                definition=changed_definition("pico-optional", optional))
        assert r.wait() == 0, r.text()
        rows = r.rows()
        assert len(rows) == len(points)
        for x in rows:
            s = float(x["set"])
            if s in over:
                assert (x["pico1_status"], x["pico1_reason"], x["pico1_mean"]) == (
                    "missing", "INVALID", "nan"), x
            else:
                assert x["pico1_status"] == "ok", x
                assert abs(float(x["pico1_mean"]) - spectrum(float(x["readback_mean"]))) \
                    <= 5 * NOISE, x
        assert read(PICO + ".STAT")["value"] is not None
    finally:
        fixed_range(0)


# --- 4: the service stops in the middle -----------------------------------------------------------

SETTLE_TIMEOUT = SHIPPED["actuator"]["settle_timeout"]


def service_back():
    service("run")
    wait_until(lambda: valid(RB), 40, "the service read again")     # asyn retries every 20 s


def test_4_service_stops_in_the_middle():
    park()
    w = Watch(SET)
    try:
        r = Run("service-stop", "--start", 8, "--stop", 14, "--step", 0.5)
        wait_until(lambda: w.last() == 10.0 or r.proc.poll() is not None, 120, "set at 10")
        time.sleep(0.3)                                  # in the settling of that point
        st = status()
        t_stop, wall_stop = time.monotonic(), time.time()
        service("stop")
        code = r.wait()
        after = w.since(t_stop)
    finally:
        w.close()
    print("test 4: exit %d after %.1f s; set PV after the stop %s" % (code, r.seconds, after))
    assert st["channels"]["o1"]["held"] == pytest.approx(10.0)    # the magnet's last set
    # The read-back goes INVALID; the program waits for it for the settle timeout and ends
    # "not settled" (the read-back INVALID is not "the actuator lost", SCAN.md section 5).
    assert code == 7, r.text()
    m = r.meta()
    assert (m["state"], m["outcome"]["reason"], m["outcome"]["point"]) == (
        "ended", "not settled", 4)
    assert "last read-back INVALID" in m["outcome"]["detail"]
    rows = r.rows()
    assert [float(x["set"]) for x in rows] == [8.0, 8.5, 9.0, 9.5, 10.0]
    assert rows[-1]["outcome"] == "not_settled"
    # The end move: its first part step goes to the IOC, which cannot send it (set PV INVALID);
    # then nothing more (correction of T27). The file says where it stopped and why.
    after_stop = [x for x in m["writes"] if time_of(x[0]) > wall_stop]
    assert [(v, p) for _, v, p in after_stop] == [(9.0, "end")], m["writes"]
    assert after == [9.0], after
    left = m["actuator_left"]
    notes = " ".join(left["notes"])
    assert "end move stopped" in notes and "INVALID after the write of 9" in notes, left
    assert "the last write before it 10" in notes, left
    assert (left["writes_in_end_move"], left["readback_reached_target"]) == (1, None), left
    assert read(SET)["severity"] == INVALID

    # The service again: it holds nothing, it received nothing; the set PV is INVALID (the
    # unconfirmed write), so check and run refuse and write nothing.
    service_back()
    st = status()
    assert (st["channels"]["o1"]["held"], sets_received(st), st["sim"]["writes"]) == (
        None, 0, 0), st
    assert read(HELD)["severity"] == INVALID
    c = Run("after-stop-check", command="check")
    assert c.wait(60) == 3, c.text()
    assert "actuator set PV dipole:current:set: INVALID" in c.text()
    r = Run("after-stop-run")
    assert r.wait(60) == 3, r.text()
    assert sets_received() == 0

    # The operator sets the magnet: the scan can start.
    park()
    c = Run("after-park-check", command="check")
    assert c.wait(60) == 0, c.text()

    # The service stopped and started while no scan runs (nothing written in between): the set
    # PV keeps its value and NO_ALARM (dipole.db: it is processed only when written), the
    # service holds nothing, its output is at the sim backend's 0 V. `check` would start from
    # 6 A: the first part step would set 7 A on an output the scan believes at 6 A. A finding
    # (SCAN.md, "The dipole scan in the emulation"): a condition on the held value refuses it.
    service("stop")
    wait_until(lambda: not valid(RB), 20, "the read-back INVALID")
    service_back()
    assert status()["channels"]["o1"]["held"] is None
    assert read(SET)["severity"] < INVALID and read(SET)["value"] == PARK
    assert read(HELD)["severity"] == INVALID
    assert read(RB)["value"] == pytest.approx(0.0, abs=TOL)
    c = Run("restarted-check", command="check")
    assert c.wait(60) == 0, c.text()
    assert "now          set 6.0, read-back 0.0" in c.text()

    def held_known(d):
        d["conditions"] = [{"pv": HELD, "op": ">=", "value": 0}]
    c = Run("restarted-held-check", command="check",
            definition=changed_definition("held-known", held_known))
    assert c.wait(60) == 3, c.text()
    assert "condition dipole:current:held >= 0: INVALID" in c.text()
    assert sets_received() == 0
    park()


# --- 5: the picoammeter goes silent in the middle -------------------------------------------------

def test_5_picoammeter_silent_in_the_middle():
    park()
    wait_until(lambda: valid(PICO), 10, "a valid picoammeter reading")
    w = Watch(SET)
    try:
        with ControlClient(SIM, 6001) as ctl:
            r = Run("pico-silent", "--start", 8, "--stop", 14, "--step", 0.5)
            wait_until(lambda: w.last() == 10.0 or r.proc.poll() is not None, 120, "set at 10")
            time.sleep(0.3)                              # in the settling of that point
            t = time.monotonic()
            ctl.fault("silent")
            try:
                code = r.wait()
                after = w.since(t)
            finally:
                ctl.clear("silent")
    finally:
        w.close()
    assert code == 6, r.text()
    rows = r.rows()
    assert [float(x["set"]) for x in rows] == [8.0, 8.5, 9.0, 9.5, 10.0]
    assert [x["pico1_status"] for x in rows] == ["ok"] * 4 + ["missing"]
    assert rows[-1]["pico1_reason"] == "INVALID"
    m = r.meta()
    assert (m["state"], m["outcome"]["reason"], m["outcome"]["point"]) == (
        "ended", "required detector lost", 4)
    assert_back_in_part_steps(after, 10.0, PARK)
    assert after == [9.0, 8.0, 7.0, 6.0]
    assert m["actuator_left"]["readback_reached_target"] is True
    st = status()
    assert st["channels"]["o1"]["held"] == pytest.approx(PARK)
    wait_until(lambda: valid(PICO), 10, "the picoammeter back")


# --- 6: an IOC restart in the middle ---------------------------------------------------------------

def test_6_ioc_restart_in_the_middle():
    park()
    w = Watch(SET)
    try:
        r = Run("ioc-restart", "--start", 8, "--stop", 14, "--step", 0.5)
        wait_until(lambda: w.last() == 10.0, 120, "set at 10")
        time.sleep(0.3)
        st0 = status()
        t, wall = time.monotonic(), time.time()
        restart_ioc()
        code = r.wait(60)
        wait_until(lambda: epics.caget("DEVTEST:heartbeat", timeout=1) is not None, 60, "IOC back")
        wait_until(lambda: valid(SET), 30, "the set record took over the held value")
        time.sleep(3.0)                                  # a late write would show now
        after = w.since(t)
    finally:
        w.close()
    assert code == 5, r.text()
    m = r.meta()
    assert m["outcome"]["reason"] == "actuator lost"
    assert m["actuator_left"]["writes_in_end_move"] == 0
    assert all(time_of(x[0]) < wall for x in m["writes"]), m["writes"]
    assert None in after, after                          # the monitor saw the IOC go
    assert set(after[after.index(None) + 1:]) <= {10.0}, after   # first contact only
    # At the service, read from the service: nothing received after the restart, the magnet
    # where the scan left it.
    st = status()
    assert sets_received(st) == sets_received(st0), (st["counts"], st0["counts"])
    assert st["channels"]["o1"]["held"] == pytest.approx(10.0)
    assert st["channels"]["i1"]["volts"] * 10.0 == pytest.approx(10.0, abs=TOL)
    assert st["sim"]["writes"] == st0["sim"]["writes"]
    assert read(SET)["value"] == pytest.approx(10.0)    # the IOC took it over, sent nothing
    park()                                               # the operator takes it back


def time_of(iso):
    import datetime
    return datetime.datetime.fromisoformat(iso).timestamp()
