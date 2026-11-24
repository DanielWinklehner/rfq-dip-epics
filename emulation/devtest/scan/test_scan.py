"""The scan program against soft records (scan.db), run as the owner runs it:
python -m mist2scan run <definition>. The tests read the files it writes and watch the set PV
with a monitor of their own.

    emulation/devtest/run.sh emulation/devtest/scan

Order matters: the IOC restart comes last (it resets every record).
"""
import csv
import glob
import json
import os
import signal
import subprocess
import sys
import threading
import time

import epics
import numpy
import pytest
import yaml

BUILD = os.environ["DEVTEST_BUILD"]
CASE = os.path.dirname(os.path.abspath(__file__))
SCANS = "/repo/scans"
SET, RB = "SCAN:x:set", "SCAN:x:get"
TOL = 0.01


class Watch:
    """Every value of a PV as a monitor delivers it: (monotonic time, value), and disconnects
    as (time, None)."""

    def __init__(self, name):
        self.events = []
        self.lock = threading.Lock()
        self.pv = epics.PV(name, auto_monitor=True, callback=self._cb,
                           connection_callback=self._conn)
        assert self.pv.wait_for_connection(5.0)

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


def definition(name, change=None):
    """A copy of scan.yaml, changed by change(data), in build/defs/<name>.yaml."""
    with open(os.path.join(CASE, "scan.yaml")) as handle:
        data = yaml.safe_load(handle)
    if change:
        change(data)
    os.makedirs(os.path.join(BUILD, "defs"), exist_ok=True)
    path = os.path.join(BUILD, "defs", name + ".yaml")
    with open(path, "w") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return path


class Run:
    """python -m mist2scan <command> <definition> [args], its output in build/<name>.log."""

    def __init__(self, name, path, *args, command="run"):
        self.out = os.path.join(BUILD, "out", name)
        self.log = os.path.join(BUILD, name + ".log")
        env = dict(os.environ, PYTHONPATH=SCANS)
        self.handle = open(self.log, "w")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mist2scan", command, path, "--output", self.out] + list(args),
            env=env, cwd=CASE, stdout=self.handle, stderr=subprocess.STDOUT)

    def wait(self, timeout=180):
        try:
            code = self.proc.wait(timeout)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            self.handle.close()
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


def wait_until(test, timeout, what):
    end = time.monotonic() + timeout
    while not test():
        if time.monotonic() > end:
            pytest.fail("no %s within %g s" % (what, timeout))
        time.sleep(0.01)


@pytest.fixture
def watch():
    epics.caput("SCAN:permit:get", 1, wait=True)
    epics.caput("SCAN:flaky:bad", 0, wait=True)
    epics.caput(SET, 0.0, wait=True)
    wait_until(lambda: epics.caget(RB, use_monitor=False) == 0.0, 5, "read-back at 0")
    w = Watch(SET)
    yield w
    w.close()


def assert_back_in_part_steps(values, start, end, max_step):
    """values: the set PV after the cause; from `start` to `end`, each step at most max_step,
    always towards the end."""
    assert values, "no write after the cause"
    assert values[-1] == pytest.approx(end)
    prev = start
    for v in values:
        assert abs(v - prev) <= max_step + 1e-6, values
        assert abs(v - end) < abs(prev - end) + 1e-9, values
        prev = v


def test_every_record_is_valid():
    for name in (SET, RB, "SCAN:peaks:get", "SCAN:hold:get", "SCAN:flaky:get",
                 "SCAN:permit:get"):
        pv = epics.PV(name, form="time")
        assert pv.get(use_monitor=False, timeout=2) is not None, name
        assert pv.severity == 0, name
    limits = epics.PV(SET).get_ctrlvars()
    assert (limits["lower_ctrl_limit"], limits["upper_ctrl_limit"]) == (-10, 10)


def test_check_writes_nothing(watch):
    t0 = time.monotonic()
    r = Run("check", os.path.join(CASE, "scan.yaml"), command="check")
    assert r.wait(30) == 0, r.text()
    assert "points       37" in r.text() and "it would start" in r.text()
    assert "set PV control limits [-10, 10]" in r.text()
    assert not os.path.exists(r.out)
    time.sleep(0.5)
    assert watch.since(t0) == []


def test_three_peaks_where_the_database_puts_them(watch):
    r = Run("peaks", os.path.join(CASE, "scan.yaml"))
    assert r.wait() == 0, r.text()
    rows = r.rows()
    assert len(rows) == 37
    assert {x["outcome"] for x in rows} == {"ok"}
    for x in rows:
        assert abs(float(x["readback_mean"]) - float(x["set"])) <= TOL
        assert abs(float(x["readback_min"]) - float(x["set"])) <= TOL
        assert abs(float(x["readback_max"]) - float(x["set"])) <= TOL
        # the detector that holds one value: counted once per point, its value, no spread
        assert (x["hold_n"], float(x["hold_mean"]), float(x["hold_spread"]),
                x["hold_status"]) == ("1", 42.0, 0.0, "ok")
        assert x["flaky_status"] == "ok"
        assert int(x["peaks_n"]) >= 3               # a new value every 0.1 s in a 0.5 s dwell
    # numpy reads the table without this program
    table = numpy.genfromtxt(os.path.join(r.directory(), "points.csv"), delimiter=",",
                             names=True, dtype=None, encoding="utf-8")
    x, y = table["readback_mean"], table["peaks_mean"]
    peaks = [k for k in range(1, len(y) - 1) if y[k] > y[k - 1] and y[k] >= y[k + 1]
             and y[k] > 0.5]
    assert len(peaks) == 3, list(zip(x, y))
    found = []
    for k in peaks:                                  # vertex of the parabola through 3 points
        y0, y1, y2 = y[k - 1], y[k], y[k + 1]
        h = x[k + 1] - x[k]
        found.append(x[k] + h * (y0 - y2) / (2 * (y0 - 2 * y1 + y2)))
    where = [float(epics.caget("SCAN:peaks:get.%s" % f)) for f in "EFG"]
    print("peaks at %s, database %s" % (["%.3f" % f for f in found], where))
    assert found == pytest.approx(where, abs=0.1)
    m = r.meta()
    assert (m["state"], m["outcome"]["code"], m["rows"]) == ("completed", 0, 37)
    assert m["pvs"][SET]["units"] == "mm"
    assert m["limits"]["control"] == [-10, 10]
    assert watch.last() == 0.0                       # back to the value before the scan
    assert m["actuator_left"]["readback_reached_target"] is True


def test_invalid_detector_missing_exactly_there(watch):
    r = Run("invalid", os.path.join(CASE, "scan.yaml"), "--start", "0", "--stop", "4",
            "--step", "0.5")
    marks = []
    while r.proc.poll() is None:
        v = watch.last()
        if v == 1.5 and not marks:
            epics.caput("SCAN:flaky:bad", 1, wait=True)
            marks.append(v)
        if v == 3.0 and len(marks) == 1:
            epics.caput("SCAN:flaky:bad", 0, wait=True)
            marks.append(v)
        time.sleep(0.005)
    assert r.wait() == 0, r.text()
    rows = r.rows()
    status = {float(x["set"]): x["flaky_status"] for x in rows}
    assert status == {0.0: "ok", 0.5: "ok", 1.0: "ok", 1.5: "missing", 2.0: "missing",
                      2.5: "missing", 3.0: "ok", 3.5: "ok", 4.0: "ok"}
    for x in rows:
        if x["flaky_status"] == "missing":
            assert (x["flaky_mean"], x["flaky_n"], x["flaky_reason"]) == ("nan", "0", "INVALID")
        else:
            assert float(x["flaky_mean"]) == pytest.approx(float(x["set"]), abs=TOL)
            assert float(x["flaky_max"]) < 100                 # never a value of +1000
        assert x["peaks_status"] == "ok"


def stop_in_the_middle(name, at, act, max_step=0.4):
    """A scan 0..8 in steps of 1 (part steps of max_step); act() when the set PV reaches `at`.
    Returns (run, exit code, the set PV's values after act)."""
    def change(d):
        d["points"] = {"start": 0.0, "stop": 8.0, "step": 1.0}
        d["actuator"]["max_step"] = max_step
    w = Watch(SET)
    try:
        r = Run(name, definition(name, change))
        wait_until(lambda: w.last() == at or r.proc.poll() is not None, 120, "set at %g" % at)
        time.sleep(0.3)                     # in the settling of that point
        t = time.monotonic()
        act(r)
        code = r.wait(60)
        time.sleep(0.5)
        return r, code, w.since(t)
    finally:
        w.close()


def test_condition_lost_ends_and_goes_back_in_part_steps(watch):
    r, code, after = stop_in_the_middle("condition", 5.0,
                                        lambda r: epics.caput("SCAN:permit:get", 0, wait=True))
    epics.caput("SCAN:permit:get", 1, wait=True)
    assert code == 4, r.text()
    assert_back_in_part_steps(after, 5.0, 0.0, 0.4)
    assert len(after) == 13                     # 5 -> 0 in steps of at most 0.4: 13 writes
    rows = r.rows()
    assert [float(x["set"]) for x in rows] == [0, 1, 2, 3, 4]
    m = r.meta()
    assert (m["state"], m["outcome"]["reason"], m["outcome"]["point"]) == (
        "ended", "condition lost", 5)
    assert "SCAN:permit:get == 1 no longer holds" in m["outcome"]["detail"]
    assert m["actuator_left"]["last_written"] == 0.0
    assert m["actuator_left"]["readback_reached_target"] is True


@pytest.mark.parametrize("signum,code", [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_signal_ends_and_goes_back_in_part_steps(watch, signum, code):
    r, got, after = stop_in_the_middle("signal%d" % signum, 4.0,
                                       lambda r: r.proc.send_signal(signum))
    assert got == code, r.text()
    assert_back_in_part_steps(after, 4.0, 0.0, 0.4)
    assert [float(x["set"]) for x in r.rows()] == [0, 1, 2, 3]
    assert r.meta()["outcome"]["code"] == code


def test_required_detector_not_connected_refused(watch):
    t0 = time.monotonic()

    def change(d):
        d["detectors"].append({"pv": "SCAN:nothere", "name": "nothere", "required": True})
        d["connect_timeout"] = 2.0
    r = Run("required", definition("required", change))
    assert r.wait(30) == 3, r.text()
    assert "detector nothere (SCAN:nothere): not connected" in r.text()
    assert not os.path.exists(r.out)
    assert watch.since(t0) == []


def test_beyond_the_control_limits_refused(watch):
    t0 = time.monotonic()

    def change(d):
        d["actuator"]["limits"] = [-20.0, 20.0]
        d["points"] = {"start": -15.0, "stop": 15.0, "step": 5.0}
    path = definition("beyond", change)
    c = Run("beyond-check", path, command="check")
    assert c.wait(30) == 3, c.text()
    r = Run("beyond", path)
    assert r.wait(30) == 3, r.text()
    assert "2 of 7 points outside the limits [-10, 10], the first -15" in r.text()
    assert not os.path.exists(r.out)
    time.sleep(0.5)
    assert watch.since(t0) == []


def test_ioc_restart_a_clean_end_and_no_write_after(watch):
    restart = os.path.join(BUILD, "ioc-restart")
    w = Watch(SET)
    try:
        r = Run("restart", os.path.join(CASE, "scan.yaml"), "--start", "0", "--stop", "6",
                "--step", "1")
        wait_until(lambda: w.last() == 3.0, 60, "set at 3")
        time.sleep(0.3)
        t = time.monotonic()
        wall = time.time()
        with open(restart, "w") as handle:
            handle.write("restart %f\n" % wall)
        code = r.wait(60)
        # the IOC is back; watch a while longer for a late write
        wait_until(lambda: epics.caget("DEVTEST:heartbeat", timeout=1) is not None, 60,
                   "IOC back")
        time.sleep(3.0)
        after = w.since(t)
    finally:
        w.close()
    assert code == 5, r.text()
    assert None in after, after                  # the monitor saw the IOC go
    back = after[after.index(None) + 1:]
    assert set(back) <= {0.0}, after             # only the restarted IOC's own value (scan.db)
    m = r.meta()
    assert m["outcome"]["reason"] == "actuator lost"
    assert m["actuator_left"]["writes_in_end_move"] == 0
    assert all(time_of(x[0]) < wall for x in m["writes"]), m["writes"]
    assert [float(x["set"]) for x in r.rows()] == [0, 1, 2]


def time_of(iso):
    import datetime
    return datetime.datetime.fromisoformat(iso).timestamp()
