"""The definition (mist2scan.definition): keys, the point list, part steps. No EPICS.

    python3 -m unittest discover -s scans/tests -t scans -v      (from the repository root)
"""
import os
import tempfile
import unittest

from mist2scan.definition import DefinitionError, load, make, part_steps, range_points


def base():
    return {
        "name": "t",
        "actuator": {"set": "X:set", "readback": "X:get", "tolerance": 0.01,
                     "settle_timeout": 5.0, "settle_time": 0.2, "max_step": 1.0,
                     "step_pause": 0.1, "limits": [-10, 10], "on_not_settled": "skip"},
        "points": {"start": 0, "stop": 2, "step": 0.5},
        "detectors": [{"pv": "D:a", "name": "a", "required": True}],
        "dwell": 0.5,
        "end": "previous",
    }


class Points(unittest.TestCase):
    def test_upwards_with_the_end_point(self):
        self.assertEqual(range_points(0, 2, 0.5), [0.0, 0.5, 1.0, 1.5, 2.0])

    def test_downwards_needs_a_negative_step(self):
        self.assertEqual(range_points(2, 0, -0.5), [2.0, 1.5, 1.0, 0.5, 0.0])
        with self.assertRaisesRegex(DefinitionError, "goes away from stop"):
            range_points(2, 0, 0.5)
        with self.assertRaisesRegex(DefinitionError, "goes away from stop"):
            range_points(0, 2, -0.5)

    def test_an_end_point_off_the_grid_is_not_added(self):
        self.assertEqual(range_points(0, 1.2, 0.5), [0.0, 0.5, 1.0])
        self.assertEqual(range_points(0, -1.2, -0.5), [0.0, -0.5, -1.0])

    def test_rounding(self):
        pts = range_points(0, 1, 0.1)
        self.assertEqual(len(pts), 11)                 # 1.0 is reached although 10 * 0.1 < 1
        self.assertEqual(pts[3], 0.3)                  # not 0.30000000000000004
        self.assertEqual(pts[-1], 1.0)
        self.assertEqual(range_points(-0.3, 0.3, 0.1), [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3])
        self.assertEqual(range_points(1e-9, 3e-9, 1e-9), [1e-9, 2e-9, 3e-9])

    def test_one_point_and_no_step(self):
        self.assertEqual(range_points(5, 5, 1), [5.0])
        with self.assertRaisesRegex(DefinitionError, "must not be 0"):
            range_points(0, 1, 0)

    def test_a_list(self):
        data = base()
        data["points"] = {"values": [3, 1, 2]}
        self.assertEqual(make(data).points, [3.0, 1.0, 2.0])
        data["points"]["start"] = 0
        with self.assertRaisesRegex(DefinitionError, "not both"):
            make(data)


class PartSteps(unittest.TestCase):
    def test_small_move_is_one_write(self):
        self.assertEqual(part_steps(0, 0.7, 1.0), [0.7])
        self.assertEqual(part_steps(0, 1.0, 1.0), [1.0])
        self.assertEqual(part_steps(0, 7, None), [7])

    def test_equal_steps_none_larger_than_max(self):
        steps = part_steps(0, 2.5, 1.0)
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[-1], 2.5)
        prev = 0
        for s in steps:
            self.assertLessEqual(abs(s - prev), 1.0 + 1e-12)
            prev = s
        down = part_steps(3.0, -1.0, 0.5)
        self.assertEqual(len(down), 8)
        self.assertEqual(down[-1], -1.0)
        self.assertTrue(all(-1.0 <= s <= 3.0 for s in down))
        self.assertEqual(down, sorted(down, reverse=True))


class Keys(unittest.TestCase):
    def test_the_base_definition_is_valid(self):
        d = make(base())
        self.assertEqual(d.points, [0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertEqual(d.pvs(), ["X:set", "X:get", "D:a"])
        self.assertEqual(d.conditions, [])

    def test_unknown_keys_are_errors(self):
        for where, key in (("", "dwel"), ("actuator", "tolerence"), ("points", "stpe")):
            data = base()
            (data[where] if where else data)[key] = 1
            with self.assertRaisesRegex(DefinitionError, "unknown key: %s" % key):
                make(data)
        data = base()
        data["detectors"][0]["requried"] = True
        with self.assertRaisesRegex(DefinitionError, r"detectors\[0\]\.unknown key: requried"):
            make(data)
        data = base()
        data["conditions"] = [{"pv": "C", "op": "==", "value": 1, "vale": 2}]
        with self.assertRaisesRegex(DefinitionError, "unknown key: vale"):
            make(data)

    def test_missing_and_wrong_values(self):
        cases = [(("actuator", "tolerance"), None, "tolerance: missing"),
                 (("actuator", "tolerance"), 0, "greater than 0"),
                 (("actuator", "limits"), [5, 1], "not below"),
                 (("actuator", "on_not_settled"), "maybe", "on_not_settled"),
                 (("end",), "home", "end:"),
                 (("dwell",), -1, "at least 0")]
        for path, value, text in cases:
            data = base()
            target = data
            for p in path[:-1]:
                target = target[p]
            if value is None:
                del target[path[-1]]
            else:
                target[path[-1]] = value
            with self.assertRaisesRegex(DefinitionError, text):
                make(data)
        data = base()
        data["detectors"][0]["required"] = "yes"
        with self.assertRaisesRegex(DefinitionError, "true or false"):
            make(data)
        data = base()
        data["conditions"] = [{"pv": "C", "op": "=", "value": 1}]
        with self.assertRaisesRegex(DefinitionError, "op:"):
            make(data)

    def test_end_and_null_max_step(self):
        data = base()
        data["end"] = 3.5
        data["actuator"]["max_step"] = None
        d = make(data)
        self.assertEqual(d.end, 3.5)
        self.assertIsNone(d.max_step)

    def test_overrides(self):
        d = make(base(), start=1, step=0.25, dwell=2, output="/tmp/x")
        self.assertEqual(d.points, [1.0, 1.25, 1.5, 1.75, 2.0])
        self.assertEqual((d.dwell, d.output), (2.0, "/tmp/x"))
        self.assertEqual(d.data["points"], {"start": 1, "stop": 2, "step": 0.25})
        data = base()
        data["points"] = {"values": [1, 2]}
        with self.assertRaisesRegex(DefinitionError, "must all be given"):
            make(data, start=0)
        self.assertEqual(make(data, start=0, stop=1, step=1).points, [0.0, 1.0])

    def test_load_from_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "d.yaml")
            with open(path, "w") as handle:
                handle.write("name: t\nactuator: {set: A}\nmystery: 1\n")
            with self.assertRaisesRegex(DefinitionError, "unknown key: mystery"):
                load(path)

    def test_the_shipped_definitions_load(self):
        here = os.path.join(os.path.dirname(__file__), "..", "config")
        names = sorted(f for f in os.listdir(here) if f.endswith(".yaml"))
        self.assertTrue(names)
        for name in names:
            d = load(os.path.join(here, name))
            self.assertTrue(all(d.limits[0] <= x <= d.limits[1] for x in d.points), name)


if __name__ == "__main__":
    unittest.main()
