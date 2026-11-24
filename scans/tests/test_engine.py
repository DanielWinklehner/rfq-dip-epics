"""The scan (mist2scan.engine) against a fake Channel Access side and a fake clock (fake.py).

Settling and its timeout, what a dwell collects, invalid and missing values, every end of the
scan with the actuator's last writes, the refusals, rows on disk after an abort. No EPICS.
"""
import csv
import json
import math
import os
import shutil
import tempfile
import unittest

from mist2scan import engine as E
from mist2scan.definition import make
from mist2scan.files import ScanFiles

from .fake import World
from .test_definition import base


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.made = []
        self.w = World(start=0.0)
        self.w.detector("D:a", lambda w: w.pvs["X:get"].value * 10.0)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def definition(self, **changes):
        data = base()
        for path, value in changes.items():
            target = data
            keys = path.split("__")
            for k in keys[:-1]:
                target = target[k]
            target[keys[-1]] = value
        return make(data)

    def scan(self, d=None, **changes):
        d = d or self.definition(**changes)
        self.s = E.Scan(d, self.w, clock=self.w.clock, sleep=self.w.sleep, wall=self.w.wall)
        return self.s

    def make_files(self, name, t):
        f = ScanFiles(self.tmp, name, t)
        self.made.append(f)
        return f

    def run_scan(self, d=None, **changes):
        self.scan(d, **changes)
        return self.s.run(self.make_files, command=["test"])

    def rows(self):
        with open(os.path.join(self.made[0].path, "points.csv")) as handle:
            return list(csv.DictReader(handle))

    def meta(self):
        with open(os.path.join(self.made[0].path, "scan.json")) as handle:
            return json.load(handle)

    def assert_steps_at_most(self, values, start, max_step):
        prev = start
        for v in values:
            self.assertLessEqual(abs(v - prev), max_step + 1e-9, values)
            prev = v


class Complete(ScanTest):
    def test_every_point_a_row_and_back_to_the_start(self):
        self.w.pvs["X:set"].value = self.w.pvs["X:get"].value = -1.5
        self.assertEqual(self.run_scan(), E.COMPLETED)
        rows = self.rows()
        self.assertEqual([float(r["set"]) for r in rows], [0.0, 0.5, 1.0, 1.5, 2.0])
        for r in rows:
            self.assertEqual(r["outcome"], "ok")
            self.assertAlmostEqual(float(r["readback_mean"]), float(r["set"]))
            self.assertAlmostEqual(float(r["a_mean"]), 10 * float(r["set"]))
            self.assertEqual(r["a_status"], "ok")
        # the first move (-1.5 -> 0) in two part steps, the end back to -1.5 from 2.0 in four
        written = self.w.written()
        self.assertEqual(written[:2], [-0.75, 0.0])
        self.assertEqual(written[-4:], [1.125, 0.25, -0.625, -1.5])
        self.assert_steps_at_most(written, -1.5, 1.0)
        m = self.meta()
        self.assertEqual((m["state"], m["outcome"]["code"], m["rows"]), ("completed", 0, 5))
        self.assertEqual(m["actuator_left"]["last_written"], -1.5)
        self.assertTrue(m["actuator_left"]["readback_reached_target"])
        self.assertEqual(m["before"], {"set": -1.5, "readback": -1.5})
        self.assertEqual(len(m["writes"]), len(written))

    def test_end_stay_and_end_value(self):
        self.assertEqual(self.run_scan(end="stay"), E.COMPLETED)
        self.assertEqual(self.w.written()[-1], 2.0)
        self.assertEqual(self.meta()["actuator_left"]["writes_in_end_move"], 0)
        self.w.writes.clear()
        self.made.clear()
        self.assertEqual(self.run_scan(end=-3.0), E.COMPLETED)      # starts at 2.0 now
        self.assertEqual(self.w.written()[-5:], [1.0, 0.0, -1.0, -2.0, -3.0])
        self.assert_steps_at_most(self.w.written(), 2.0, 1.0)

    def test_the_file_says_running_while_the_scan_runs(self):
        seen = []
        self.w.when(lambda w: w.t > 1002.0, lambda w: seen.append(self.meta()["state"]))
        self.run_scan()
        self.assertEqual(seen, ["running"])

    def test_only_the_set_pv_is_written_and_only_within_the_limits(self):
        # World.write asserts both; the limits of the definition are inside the control limits
        self.w.pvs["X:set"].lo, self.w.pvs["X:set"].hi = -5.0, 5.0
        self.run_scan(actuator__limits=[-20, 20])
        self.assertEqual(self.meta()["limits"]["effective"], [-5.0, 5.0])
        self.assertTrue(all(name == "X:set" for _, name, _ in self.w.writes))


class Settling(ScanTest):
    def test_nothing_from_before_the_settle_is_used(self):
        # The detector shows 999 while the read-back is outside the tolerance: none of it may
        # reach the row, however the monitors deliver it.
        self.w.lag = 0.3
        self.w.detectors.clear()
        self.w.detector("D:a", lambda w: 999.0 if abs(w.pvs["X:get"].value
                                                       - w.pvs["X:set"].value) > 0.01
                        else w.pvs["X:set"].value)
        self.assertEqual(self.run_scan(), E.COMPLETED)
        for r in self.rows():
            self.assertEqual(float(r["a_max"]), float(r["set"]))
            self.assertLessEqual(abs(float(r["readback_mean"]) - float(r["set"])), 0.01)

    def test_settle_time_and_dwell_are_waited(self):
        self.w.lag = 0.2
        times = []
        self.w.read_hook = lambda w, name: times.append((w.t, name))
        self.run_scan(actuator__settle_time=0.7, dwell=1.3)
        # per point: the fresh reads of the dwell; between them at least settle_time + dwell
        starts = sorted({t for t, n in times if n == "X:get"})[1:]     # [0]: prepare()
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertTrue(all(g >= 0.7 + 1.3 - 1e-9 for g in gaps), gaps)

    def test_not_settled_skip_goes_on(self):
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0, lambda w: setattr(w, "follow", False))
        self.w.when(lambda w: w.pvs["X:set"].value == 1.5, lambda w: setattr(w, "follow", True))
        t0 = self.w.t
        self.assertEqual(self.run_scan(), E.COMPLETED)
        rows = self.rows()
        self.assertEqual([r["outcome"] for r in rows],
                         ["ok", "ok", "not_settled", "ok", "ok"])
        self.assertEqual(rows[2]["a_status"], "missing")
        self.assertIn("not settled within 5 s, last read-back 0.5", rows[2]["readback_reason"])
        self.assertGreater(self.w.t - t0, 5.0)

    def test_not_settled_end(self):
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0, lambda w: setattr(w, "follow", False))
        self.assertEqual(self.run_scan(actuator__on_not_settled="end"), E.NOT_SETTLED)
        self.assertEqual([r["outcome"] for r in self.rows()], ["ok", "ok", "not_settled"])
        self.assertEqual(self.w.written()[-1], 0.0)            # back to the start
        self.assertEqual(self.meta()["outcome"]["reason"], "not settled")

    def test_an_invalid_readback_is_not_settled(self):
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0,
                    lambda w: w.post("X:get", severity=3))
        self.w.when(lambda w: w.pvs["X:set"].value == 1.5,
                    lambda w: w.post("X:get", severity=0))
        self.run_scan()
        self.assertEqual(self.rows()[2]["outcome"], "not_settled")
        self.assertIn("INVALID", self.rows()[2]["readback_reason"])


class Values(ScanTest):
    def test_invalid_detector_is_missing_at_exactly_those_points(self):
        self.w.add("D:b", 5.0)
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0, lambda w: w.post("D:b", 1e9, 3))
        self.w.when(lambda w: w.pvs["X:set"].value == 1.5, lambda w: w.post("D:b", 5.0, 0))
        d = self.definition(detectors=[{"pv": "D:a", "name": "a", "required": True},
                                       {"pv": "D:b", "name": "b", "required": False}])
        self.assertEqual(self.run_scan(d), E.COMPLETED)
        rows = self.rows()
        self.assertEqual([r["b_status"] for r in rows], ["ok", "ok", "missing", "ok", "ok"])
        self.assertEqual(rows[2]["b_mean"], "nan")
        self.assertEqual(rows[2]["b_reason"], "INVALID")
        self.assertEqual([r["b_n"] for r in rows], ["1", "1", "0", "1", "1"])   # holds: one value
        self.assertEqual(float(rows[3]["b_mean"]), 5.0)

    def test_invalid_during_part_of_the_dwell(self):
        self.w.add("D:b", 5.0)
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0,
                    lambda w: w.at(0.2 + 0.25, lambda w: w.post("D:b", 1e9, 3)))
        d = self.definition(detectors=[{"pv": "D:a", "name": "a", "required": True},
                                       {"pv": "D:b", "name": "b", "required": False}],
                            dwell=1.0)
        self.run_scan(d)
        r = self.rows()[2]
        self.assertEqual((r["b_status"], float(r["b_mean"]), float(r["b_max"])),
                         ("partial", 5.0, 5.0))
        self.assertLess(float(r["b_valid"]), 0.4)
        self.assertEqual(self.rows()[3]["b_status"], "missing")      # still INVALID

    def test_optional_detector_not_connected_at_the_start(self):
        self.w.add("D:b", 5.0, connected=False)
        d = self.definition(detectors=[{"pv": "D:a", "name": "a", "required": True},
                                       {"pv": "D:b", "name": "b", "required": False}])
        self.assertEqual(self.run_scan(d), E.COMPLETED)
        self.assertEqual({r["b_reason"] for r in self.rows()}, {"not connected"})
        self.assertIn("optional", " ".join(self.meta()["warnings"]))

    def test_disconnect_during_the_dwell_and_a_value_after(self):
        self.w.add("D:b", 5.0)
        self.w.when(lambda w: w.pvs["X:set"].value == 0.5,
                    lambda w: w.at(0.2 + 0.1, lambda w: w.disconnect("D:b")))
        self.w.when(lambda w: w.pvs["X:set"].value == 0.5,
                    lambda w: w.at(0.2 + 0.4, lambda w: w.reconnect("D:b")))
        d = self.definition(detectors=[{"pv": "D:a", "name": "a", "required": True},
                                       {"pv": "D:b", "name": "b", "required": False}])
        self.run_scan(d)
        r = self.rows()[1]
        self.assertEqual((r["b_status"], r["b_reason"], r["b_n"]),
                         ("partial", "not connected", "2"))

    def test_required_detector_invalid_for_a_whole_point_ends_the_scan(self):
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0, lambda w: w.post("D:a", severity=3))
        self.assertEqual(self.run_scan(), E.DETECTOR)
        rows = self.rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2]["a_status"], "missing")
        self.assertEqual(self.w.written()[-1], 0.0)


class Ends(ScanTest):
    """Each end: the code, the rows so far on disk, the actuator's writes after the cause."""

    def setUp(self):
        ScanTest.setUp(self)
        self.d = self.definition(points={"start": 0, "stop": 6, "step": 1},
                                 actuator__max_step=0.4)
        self.cause = None

    def at_point(self, value, fn):
        def act(w):
            self.cause = w.t
            fn(w)
        self.w.when(lambda w: w.pvs["X:set"].value == value,
                    lambda w: w.at(0.4, act))           # in the dwell of that point

    def check_back_in_part_steps(self, after_value):
        after = self.w.written(after=self.cause)
        self.assertEqual(after[-1], 0.0)
        self.assert_steps_at_most(after, after_value, 0.4)
        self.assertEqual(after, sorted(after, reverse=True))

    def test_completed(self):
        self.assertEqual(self.run_scan(self.d), E.COMPLETED)
        self.assertEqual(len(self.rows()), 7)

    def test_condition_lost(self):
        self.w.add("C:ok", 1)
        d = self.definition(points={"start": 0, "stop": 6, "step": 1}, actuator__max_step=0.4,
                            conditions=[{"pv": "C:ok", "op": "==", "value": 1}])
        self.at_point(4.0, lambda w: w.post("C:ok", 0))
        self.assertEqual(self.run_scan(d), E.CONDITION)
        self.assertEqual(len(self.rows()), 4)          # 0..3 done, 4 interrupted in its dwell
        self.check_back_in_part_steps(4.0)
        m = self.meta()
        self.assertEqual((m["state"], m["outcome"]["reason"], m["outcome"]["point"],
                          m["outcome"]["phase"]), ("ended", "condition lost", 4, "dwell"))
        self.assertIn("C:ok == 1 no longer holds", m["outcome"]["detail"])
        self.assertTrue(m["actuator_left"]["readback_reached_target"])

    def test_condition_invalid_or_disconnected(self):
        self.w.add("C:ok", 1)
        d = self.definition(conditions=[{"pv": "C:ok", "op": ">=", "value": 1}])
        self.w.when(lambda w: w.pvs["X:set"].value == 1.0, lambda w: w.post("C:ok", severity=3))
        self.assertEqual(self.run_scan(d), E.CONDITION)
        self.assertIn("INVALID", self.meta()["outcome"]["detail"])

    def test_sigint_and_sigterm(self):
        for signum, code in ((2, E.SIGINT), (15, E.SIGTERM)):
            self.w = World(start=0.0)
            self.w.detector("D:a", lambda w: 1.0)
            self.made.clear()
            self.at_point(3.0, lambda w: self.s.request_stop(signum))
            self.assertEqual(self.run_scan(self.d), code)
            self.assertEqual(len(self.rows()), 3)
            self.check_back_in_part_steps(3.0)
            self.assertEqual(self.meta()["outcome"]["code"], code)

    def test_a_second_signal_does_not_stop_the_end_move(self):
        self.at_point(3.0, lambda w: self.s.request_stop(2))
        self.w.when(lambda w: self.s.ending, lambda w: self.s.request_stop(2))
        self.assertEqual(self.run_scan(self.d), E.SIGINT)
        self.check_back_in_part_steps(3.0)

    def test_actuator_lost_nothing_written_after(self):
        self.at_point(2.0, lambda w: w.disconnect("X:set"))
        self.w.when(lambda w: w.t > (self.cause or 1e99) + 0.3,
                    lambda w: w.reconnect("X:set"))        # an IOC restart: back quickly
        self.assertEqual(self.run_scan(self.d), E.ACTUATOR)
        self.assertEqual(self.w.written(after=self.cause), [])
        m = self.meta()
        self.assertEqual(m["actuator_left"]["writes_in_end_move"], 0)
        self.assertIn("nothing written", " ".join(m["actuator_left"]["notes"]))
        self.assertEqual(len(self.rows()), 2)

    def test_readback_lost_is_the_actuator_lost(self):
        self.at_point(2.0, lambda w: w.disconnect("X:get"))
        self.assertEqual(self.run_scan(self.d), E.ACTUATOR)
        self.assertEqual(self.w.written(after=self.cause), [])

    def test_set_pv_invalid_ends(self):
        self.at_point(2.0, lambda w: w.post("X:set", severity=3))
        self.assertEqual(self.run_scan(self.d), E.ACTUATOR)
        self.assertIn("INVALID", self.meta()["outcome"]["detail"])

    def test_required_detector_lost(self):
        self.at_point(5.0, lambda w: w.disconnect("D:a"))
        self.assertEqual(self.run_scan(self.d), E.DETECTOR)
        self.assertEqual(len(self.rows()), 5)
        self.check_back_in_part_steps(5.0)

    def test_program_error(self):
        def boom(w, name):
            if w.pvs["X:set"].value == 3.0:
                raise ZeroDivisionError("a bug")
        self.w.read_hook = boom
        self.cause = None
        self.w.when(lambda w: w.pvs["X:set"].value == 3.0,
                    lambda w: setattr(self, "cause", w.t))
        self.assertEqual(self.run_scan(self.d), E.ERROR)
        self.assertEqual(len(self.rows()), 3)
        self.check_back_in_part_steps(3.0)
        self.assertIn("ZeroDivisionError: a bug", self.meta()["outcome"]["detail"])

    def test_the_end_move_stops_where_the_actuator_cannot_be_written(self):
        self.w.add("C:ok", 1)
        d = self.definition(points={"start": 0, "stop": 6, "step": 1}, actuator__max_step=0.4,
                            conditions=[{"pv": "C:ok", "op": "==", "value": 1}])
        self.at_point(4.0, lambda w: w.post("C:ok", 0))
        self.w.when(lambda w: len(w.written(after=self.cause or 1e99)) == 3,
                    lambda w: w.disconnect("X:set"))
        self.assertEqual(self.run_scan(d), E.CONDITION)
        self.assertEqual(len(self.w.written(after=self.cause)), 3)
        notes = " ".join(self.meta()["actuator_left"]["notes"])
        self.assertIn("end move stopped", notes)
        self.assertAlmostEqual(self.meta()["actuator_left"]["last_written"], 2.8)


    def test_the_end_move_stops_when_the_ioc_does_not_confirm_a_write(self):
        # T27: the DAQ service stopped, the IOC cannot send: the set PV goes INVALID after the
        # first write of the end move. Nothing more is written (section 5: set PV INVALID is
        # the actuator lost), and the file says so.
        self.w.add("C:ok", 1)
        d = self.definition(points={"start": 0, "stop": 6, "step": 1}, actuator__max_step=0.4,
                            conditions=[{"pv": "C:ok", "op": "==", "value": 1}])
        self.at_point(4.0, lambda w: w.post("C:ok", 0))
        self.w.when(lambda w: len(w.written(after=self.cause or 1e99)) == 1,
                    lambda w: w.post("X:set", severity=3))
        self.assertEqual(self.run_scan(d), E.CONDITION)
        self.assertEqual(self.w.written(after=self.cause), [3.6])
        left = self.meta()["actuator_left"]
        notes = " ".join(left["notes"])
        self.assertIn("end move stopped", notes)
        self.assertIn("X:set INVALID after the write of 3.6", notes)
        self.assertIn("the last write before it 4", notes)
        self.assertEqual(left["writes_in_end_move"], 1)
        self.assertIsNone(left["readback_reached_target"])


class Refusals(ScanTest):
    def refused(self, d=None, **changes):
        self.scan(d, **changes)
        with self.assertRaises(E.Refused) as ctx:
            self.s.run(self.make_files)
        self.assertEqual(self.w.writes, [])
        self.assertEqual(self.made, [])                 # no directory, no file
        self.assertEqual(os.listdir(self.tmp), [])
        return " | ".join(ctx.exception.reasons)

    def test_actuator_not_connected_or_invalid(self):
        self.w.pvs["X:set"].connected = False
        self.assertIn("actuator set PV X:set: not connected", self.refused())
        self.w.pvs["X:set"].connected = True
        self.w.pvs["X:get"].severity = 3
        self.assertIn("actuator read-back X:get: INVALID", self.refused())

    def test_required_detector_not_connected_or_invalid(self):
        self.w.pvs["D:a"].connected = False
        self.assertIn("detector a (D:a): not connected", self.refused())
        self.w.pvs["D:a"].connected = True
        self.w.pvs["D:a"].severity = 3
        self.assertIn("detector a (D:a): INVALID", self.refused())

    def test_condition_does_not_hold(self):
        self.w.add("C:ok", 0)
        self.assertIn("C:ok == 1 does not hold: C:ok is 0",
                      self.refused(conditions=[{"pv": "C:ok", "op": "==", "value": 1}]))
        self.assertIn("C:none == 1: not connected",
                      self.refused(conditions=[{"pv": "C:none", "op": "==", "value": 1}]))

    def test_points_outside_the_definitions_limits(self):
        self.assertIn("2 of 5 points outside the limits [-10, 1], the first 1.5",
                      self.refused(actuator__limits=[-10, 1]))

    def test_points_outside_the_control_limits(self):
        self.w.pvs["X:set"].lo, self.w.pvs["X:set"].hi = -1.0, 1.0
        self.assertIn("outside the limits [-1, 1]", self.refused())

    def test_actuator_now_outside_the_limits(self):
        self.w.pvs["X:set"].value = 12.0
        self.assertIn("the set PV is at 12, outside the limits", self.refused())

    def test_end_value_outside(self):
        self.assertIn("end value 11 outside", self.refused(end=11.0))

    def test_limits_that_do_not_overlap(self):
        self.w.pvs["X:set"].lo, self.w.pvs["X:set"].hi = 20.0, 30.0
        self.assertIn("do not overlap", self.refused())

    def test_every_reason_is_listed(self):
        self.w.pvs["D:a"].connected = False
        text = self.refused(actuator__limits=[-10, 1], end=11.0)
        self.assertEqual(text.count(" | "), 2)


class CheckPlan(ScanTest):
    def test_prepare_returns_the_plan_and_writes_nothing(self):
        plan = self.scan(actuator__settle_time=1.0, dwell=2.0).prepare()
        self.assertEqual(plan["points"], [0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertEqual(plan["estimate_s"][0], 5 * 3.0 + 0.1)   # 2.0 -> 0 in two part steps
        self.assertEqual(plan["estimate_s"][1], 5 * 3.0 + 0.1 + 6 * 5.0)
        self.assertEqual(plan["pvs"]["X:set"]["units"], "A")
        self.assertEqual(self.w.writes, [])


if __name__ == "__main__":
    unittest.main()
