"""The dipole scan with its three parts together (task T27): the shipped scan program
(scans/mist2scan) runs the shipped definition (scans/config/dipole.yaml) through one IOC
(dipole.db, picoammeter.db) against the DAQ service (daq/mist2daq, sim backend) and the Keithley
6485 simulator, coupled by coupling.py (a spectrum of three peaks over the magnet current; a model
of this case, coupling.yaml).

    emulation/devtest/run.sh emulation/devtest/dipolescan

Only the command line's overrides (--start, --stop, --step, --dwell, --output) change the run;
where a test needs anything else of the definition it says so (a finding, not a second
definition). The service's status port (6000) gives what the IOC cannot: what the service holds
and wrote, and which commands reached it.

Every test sets its own preconditions (the fixture `ready`, or test 1 its own power-on state), so
that each one passes alone (run.sh ... -k <name>) as well as in the order of this file.
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
    """The operator's set of the magnet before a scan; waits for the read-back and for the
    held value."""
    put(SET, value)
    wait_until(lambda: valid(RB) and abs(read(RB)["value"] - value) <= TOL / 5 and valid(HELD)
               and read(HELD)["value"] == value, 20, "read-back and held at %g" % value)


def assert_back_in_part_steps(values, start, end):
    assert values, "no write after the cause"
    assert values[-1] == pytest.approx(end)
    prev = start
    for v in values:
        assert abs(v - prev) <= MAX_STEP + 1e-6, values
        assert abs(v - end) < abs(prev - end) + 1e-9, values
        prev = v


def table(run):
    return numpy.genfromtxt(os.path.join(run.directory(), "points.csv"), delimiter=",",
                            names=True, dtype=None, encoding="utf-8")


# --- preconditions ---------------------------------------------------------------------------------

def service_running():
    """The DAQ service runs and the IOC reads it."""
    with open(os.path.join(BUILD, "daq-run")) as f:
        if f.read().strip() != "run":
            service("run")
    wait_until(lambda: valid(RB), 40, "the service read")        # asyn retries every 20 s


def restart_service():
    """Stop and start the service: afterwards it holds nothing."""
    service("stop")
    wait_until(lambda: not valid(RB), 20, "the read-back INVALID")
    service("run")
    wait_until(lambda: valid(RB), 40, "the service read again")


def picoammeter(ctl, zero_check):
    """No fault left, power on, autorange, zero check as asked (through the PVs)."""
    ctl.clear()
    if ctl.get("power")["external"]:
        ctl.set("power", 1)
        ctl.release("power")
    put("pico1:range:set", 0)
    wait_until(lambda: valid("pico1:zcheck:get") and read("pico1:_auto")["value"] == 1, 15,
               "autorange")
    put("pico1:zcheck:set", 1 if zero_check else 0)
    wait_until(lambda: read("pico1:zcheck:get")["value"] == (1 if zero_check else 0)
               and valid("pico1:zcheck:get"), 15, "zero check %s" % zero_check)
    if not zero_check:
        wait_until(lambda: valid(PICO), 15, "a valid picoammeter reading")


def power_cycle(ctl):
    """The picoammeter switched off and on: its power-on state (zero check ON)."""
    ctl.clear()
    ctl.set("power", 0)
    wait_until(lambda: read(PICO)["severity"] == INVALID, 10, "the picoammeter silent")
    ctl.set("power", 1)
    ctl.release("power")
    wait_until(lambda: valid("pico1:zcheck:get") and read("pico1:zcheck:get")["value"] == 1, 15,
               "zero check ON after power-on")


@pytest.fixture
def ready():
    """What every scan test starts from, whatever ran before: the service running, the
    picoammeter on, without a fault, on autorange, zero check off, the set record not in
    simulation mode, the magnet parked at PARK (the service holds it)."""
    service_running()
    put(SET + ".SIMM", 0)
    with ControlClient(SIM, 6001) as ctl:
        picoammeter(ctl, zero_check=False)
    park()
    assert status()["channels"]["o1"]["held"] == pytest.approx(PARK)


def time_of(iso):
    import datetime
    return datetime.datetime.fromisoformat(iso).timestamp()


# --- 0: the parts are there ------------------------------------------------------------------------

def test_every_part_connects():
    for name in (SET, HELD, RB, PICO, "pico1:zcheck:set", "pico1:range:set", "dipole:id"):
        assert epics.PV(name).wait_for_connection(5), name
    wait_until(lambda: valid(RB) and valid("pico1:zcheck:get"), 40, "service and picoammeter read")
    magnet = status()["channels"]["i1"]["volts"] * 10.0
    with ControlClient(SIM, 6001) as c:
        x = c.get("current")
    assert x["external"] is True, x                    # the coupling holds the input
    assert x["value"] == pytest.approx(spectrum(magnet), rel=1e-3)


# --- 1: after power-on the scan refuses ------------------------------------------------------------

def test_1_after_power_on_the_scan_refuses_and_writes_nothing():
    # Preconditions: the picoammeter in its power-on state, the service just started.
    service_running()
    with ControlClient(SIM, 6001) as ctl:
        ctl.clear()
        if read("pico1:zcheck:get")["value"] != 1:
            power_cycle(ctl)
    if status()["channels"]["o1"]["held"] is not None:
        restart_service()
    st = status()
    assert st["channels"]["o1"]["held"] is None and sets_received(st) == 0, st
    assert read(HELD)["severity"] == INVALID
    assert read(PICO)["severity"] == INVALID and read(PICO + ".STAT")["value"] == 7   # STATE

    held_reason = ("actuator held PV dipole:current:held: INVALID (UDF): the value the device "
                   "holds is not known")
    pico_reason = "detector pico1 (pico1:current:get): INVALID (STATE)"
    c = Run("refused-check", command="check")
    assert c.wait(60) == 3, c.text()
    assert held_reason in c.text() and pico_reason in c.text(), c.text()
    r = Run("refused-run")
    assert r.wait(60) == 3, r.text()
    assert "refused, nothing written" in r.text()
    assert held_reason in r.text() and pico_reason in r.text(), r.text()
    assert not os.path.exists(r.out)
    st = status()
    assert (sets_received(st), st["sim"]["writes"]) == (0, 0), st

    # The operator sets the magnet once (the service's held value becomes known); the
    # picoammeter still refuses the scan.
    park()
    n = sets_received()
    r = Run("refused-zcheck")
    assert r.wait(60) == 3, r.text()
    assert pico_reason in r.text()
    assert "actuator" not in r.text().split("refused, nothing written")[1]
    assert sets_received() == n

    # Zero check off through its PV: the scan would start.
    put("pico1:zcheck:set", 0)
    wait_until(lambda: valid(PICO), 10, "a valid picoammeter reading")
    c = Run("start-check", command="check")
    assert c.wait(60) == 0, c.text()
    assert "it would start" in c.text()
    assert "held 6.0 (dipole:current:held)" in c.text()
    assert "at least" in c.text() and "a lower bound" in c.text()
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


def per_point(r):
    t = table(r)
    el = list(t["elapsed_s"])
    return t, [b - a for a, b in zip(el, el[1:])]


def test_2_the_spectrum(ready):
    step = 0.5
    r = Run("spectrum", "--start", 7.0, "--stop", 19.5, "--step", step)   # the shipped dwell
    assert r.wait() == 0, r.text()
    rows = r.rows()
    assert len(rows) == 26
    assert {x["outcome"] for x in rows} == {"ok"}
    for x in rows:
        assert abs(float(x["readback_mean"]) - float(x["set"])) <= TOL
        assert x["pico1_status"] == "ok"
    t, pp = per_point(r)
    x, y = t["readback_mean"], t["pico1_mean"]
    found = find_peaks(x, y)
    print("peaks found at %s A, coupling %s A" % (["%.3f" % f for f, _ in found],
                                                 ["%.3f" % p for p in PEAKS]))
    assert len(found) == 3, list(zip(x, y))
    for (f, k), p in zip(found, PEAKS):
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
    n = [int(v) for v in t["pico1_n"]]
    print("R4 dwell %g s: pico1_n per point %s; time per point %.2f to %.2f s, mean %.2f s; "
          "scan %.1f s, check's lower bound %s"
          % (SHIPPED["dwell"], n, min(pp), max(pp), sum(pp) / len(pp), m["duration_s"],
             m["estimate_s"]))
    assert all(int(SHIPPED["dwell"]) <= k <= int(SHIPPED["dwell"]) + 2 for k in n), n


# --- R4: values per point against the dwell --------------------------------------------------------

@pytest.mark.parametrize("dwell", [1.0, 5.0])
def test_r4_values_per_point(ready, dwell):
    """Three points on the background with another dwell than the shipped one: how many
    picoammeter values a point gets, and the time per point (printed for SCAN.md)."""
    r = Run("dwell%g" % dwell, "--start", 7.0, "--stop", 8.0, "--step", 0.5, "--dwell", dwell)
    assert r.wait() == 0, r.text()
    t, pp = per_point(r)
    n = [int(v) for v in t["pico1_n"]]
    print("R4 dwell %g s: pico1_n %s, time per point %s s"
          % (dwell, n, ["%.2f" % v for v in pp]))
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


def test_3_overflow_at_a_peak(ready):
    fixed_range(RANGE_20NA)
    points = numpy.arange(8.0, 16.01, 0.5)
    over = [x for x in points if spectrum(x) > OVERFLOW_A]
    assert over == [9.5, 10.0, 10.5]
    assert all(abs(spectrum(x) - OVERFLOW_A) > 20 * NOISE for x in points)   # no point near it
    try:
        # As shipped (the picoammeter required): the first point on the peak ends the scan.
        w = Watch(SET)
        try:
            r = Run("overflow-shipped", "--start", 8, "--stop", 16, "--step", 0.5, "--dwell", 1)
            code = r.wait()
            after = w.since(w.events[0][0])
        finally:
            w.close()
        assert code == 6, r.text()
        rows = r.rows()
        assert [float(x["set"]) for x in rows] == [8.0, 8.5, 9.0, 9.5]
        assert [x["pico1_status"] for x in rows] == ["ok", "ok", "ok", "missing"]
        assert (rows[-1]["pico1_reason"], rows[-1]["pico1_n"]) == ("INVALID (STATE)", "0")
        assert r.meta()["outcome"]["reason"] == "required detector lost"
        k = after.index(9.5)
        assert_back_in_part_steps(after[k + 1:], 9.5, PARK)
        assert status()["channels"]["o1"]["held"] == pytest.approx(PARK)

        # With the picoammeter optional (one key changed: a finding, see SCAN.md): the scan
        # completes, the points on the peak missing with their reason, the others measured.
        def optional(d):
            d["detectors"][0]["required"] = False
        r = Run("overflow", "--start", 8, "--stop", 16, "--step", 0.5, "--dwell", 1,
                definition=changed_definition("pico-optional", optional))
        assert r.wait() == 0, r.text()
        rows = r.rows()
        assert len(rows) == len(points)
        for x in rows:
            s = float(x["set"])
            if s in over:
                assert (x["pico1_status"], x["pico1_reason"], x["pico1_mean"]) == (
                    "missing", "INVALID (STATE)", "nan"), x
            else:
                assert x["pico1_status"] == "ok", x
                assert abs(float(x["pico1_mean"]) - spectrum(float(x["readback_mean"]))) \
                    <= 5 * NOISE, x
    finally:
        fixed_range(0)


# --- 4: what the service holds; the service stops in the middle ----------------------------------

HELD_UNKNOWN = ("actuator held PV dipole:current:held: INVALID (UDF): the value the device holds "
                "is not known")


def test_4a_set_pv_differs_from_what_the_service_holds(ready):
    """The set record shows 7 A while the service holds 6 A (made here by writing the record in
    simulation mode, so that nothing is sent): refused, both values named, nothing written."""
    n = sets_received()
    put(SET + ".SIMM", 1)
    try:
        put(SET, 7.0)
    finally:
        put(SET + ".SIMM", 0)
    assert read(SET)["value"] == 7.0 and read(HELD)["value"] == PARK
    c = Run("differs-check", command="check")
    assert c.wait(60) == 3, c.text()
    reason = ("the set PV dipole:current:set shows 7, the device holds 6 (dipole:current:held): "
              "more than the tolerance 0.05 apart")
    assert reason in c.text(), c.text()
    r = Run("differs-run")
    assert r.wait(60) == 3, r.text()
    assert reason in r.text()
    assert sets_received() == n


def test_4b_service_restarted_with_no_scan_running(ready):
    """Stopped and started while no scan runs: the set record keeps 6 A and NO_ALARM, the service
    holds nothing. check and run refuse: what the device holds is not known."""
    restart_service()
    assert status()["channels"]["o1"]["held"] is None
    assert read(SET)["severity"] < INVALID and read(SET)["value"] == PARK
    assert read(HELD)["severity"] == INVALID
    c = Run("restarted-check", command="check")
    assert c.wait(60) == 3, c.text()
    assert HELD_UNKNOWN in c.text(), c.text()
    r = Run("restarted-run")
    assert r.wait(60) == 3, r.text()
    assert HELD_UNKNOWN in r.text()
    st = status()
    assert (sets_received(st), st["sim"]["writes"]) == (0, 0), st


def test_4c_service_stops_in_the_middle(ready):
    w = Watch(SET)
    try:
        r = Run("service-stop", "--start", 8, "--stop", 14, "--step", 0.5, "--dwell", 1)
        wait_until(lambda: w.last() == 10.0 or r.proc.poll() is not None, 120, "set at 10")
        time.sleep(0.3)                                  # in the settling of that point
        st = status()
        t_stop, wall_stop = time.monotonic(), time.time()
        service("stop")
        code = r.wait()
        t_end = time.monotonic()
        time.sleep(2.0)                                  # a late write would show now
        after = w.since(t_stop)
    finally:
        w.close()
    m = r.meta()
    seconds = time_of(m["end_time"]) - wall_stop
    print("test 4c: exit %d, %.2f s after the stop (process ended after %.2f s); %s"
          % (code, seconds, t_end - t_stop, m["outcome"]["detail"]))
    assert st["channels"]["o1"]["held"] == pytest.approx(10.0)    # the magnet's last set
    assert code == 5, r.text()
    assert (m["state"], m["outcome"]["reason"], m["outcome"]["point"]) == (
        "ended", "actuator lost", 4)
    assert "INVALID" in m["outcome"]["detail"]
    assert seconds < 5.0                    # the IOC's report, not the settle timeout (30 s)
    # nothing written after it: by the program, at the IOC, at the service
    assert all(time_of(x[0]) < wall_stop for x in m["writes"]), m["writes"]
    assert m["actuator_left"]["writes_in_end_move"] == 0
    assert after == [], after
    rows = r.rows()
    assert [float(x["set"]) for x in rows] == [8.0, 8.5, 9.0, 9.5]
    service("run")
    wait_until(lambda: valid(RB), 40, "the service read again")
    st = status()
    assert (st["channels"]["o1"]["held"], sets_received(st), st["sim"]["writes"]) == (
        None, 0, 0), st
    c = Run("after-stop-check", command="check")
    assert c.wait(60) == 3, c.text()
    assert HELD_UNKNOWN in c.text()


# --- 5: the picoammeter goes silent in the middle -------------------------------------------------

def test_5_picoammeter_silent_in_the_middle(ready):
    w = Watch(SET)
    try:
        with ControlClient(SIM, 6001) as ctl:
            r = Run("pico-silent", "--start", 8, "--stop", 14, "--step", 0.5, "--dwell", 1)
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
    print("test 5: reason %r" % rows[-1]["pico1_reason"])
    assert rows[-1]["pico1_reason"].startswith("INVALID (")
    assert rows[-1]["pico1_reason"] != "INVALID (STATE)"          # not a reading, the line
    m = r.meta()
    assert (m["state"], m["outcome"]["reason"], m["outcome"]["point"]) == (
        "ended", "required detector lost", 4)
    assert_back_in_part_steps(after, 10.0, PARK)
    assert after == [9.0, 8.0, 7.0, 6.0]
    assert m["actuator_left"]["readback_reached_target"] is True
    assert status()["channels"]["o1"]["held"] == pytest.approx(PARK)
    wait_until(lambda: valid(PICO), 10, "the picoammeter back")


# --- 6: an IOC restart in the middle ---------------------------------------------------------------

def test_6_ioc_restart_in_the_middle(ready):
    w = Watch(SET)
    try:
        r = Run("ioc-restart", "--start", 8, "--stop", 14, "--step", 0.5, "--dwell", 1)
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
