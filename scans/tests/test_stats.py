"""The statistics of one dwell (mist2scan.stats) with constructed sequences. No EPICS."""
import math
import unittest

from mist2scan.stats import summarize


class Stats(unittest.TestCase):
    def test_a_value_that_holds_for_the_whole_dwell_counts_once(self):
        s = summarize([(0.0, 4.2, None)], 0.0, 1.0)
        self.assertEqual((s.mean, s.spread, s.n, s.minimum, s.maximum), (4.2, 0.0, 1, 4.2, 4.2))
        self.assertEqual((s.status, s.valid, s.reason), ("ok", 1.0, ""))

    def test_steps_are_weighted_by_the_time_they_hold(self):
        # 1.0 for 0.75 s, then 3.0 for 0.25 s: the signal's mean is 1.5, not (1 + 3) / 2
        s = summarize([(0.0, 1.0, None), (0.75, 3.0, None)], 0.0, 1.0)
        self.assertAlmostEqual(s.mean, 1.5)
        self.assertAlmostEqual(s.spread, math.sqrt(0.75 * 0.25 + 0.25 * 2.25))
        self.assertEqual((s.n, s.minimum, s.maximum), (2, 1.0, 3.0))

    def test_a_burst_of_updates_does_not_outweigh_a_long_value(self):
        samples = [(0.0, 10.0, None)] + [(0.9 + k * 0.01, 0.0, None) for k in range(10)]
        s = summarize(samples, 0.0, 1.0)
        self.assertAlmostEqual(s.mean, 9.0)
        self.assertEqual(s.n, 11)

    def test_invalid_stretches_are_left_out(self):
        # valid 2.0 for 0.4 s, INVALID (value 1e9 at the IOC) for 0.4 s, valid 4.0 for 0.2 s
        s = summarize([(0.0, 2.0, None), (0.4, None, "INVALID"), (0.8, 4.0, None)], 0.0, 1.0)
        self.assertAlmostEqual(s.mean, (2.0 * 0.4 + 4.0 * 0.2) / 0.6)
        self.assertAlmostEqual(s.valid, 0.6)
        self.assertEqual((s.status, s.reason, s.n, s.maximum), ("partial", "INVALID", 2, 4.0))

    def test_no_valid_value_is_missing_never_an_older_one(self):
        s = summarize([(0.0, None, "INVALID"), (0.5, None, "not connected")], 0.0, 1.0)
        self.assertTrue(math.isnan(s.mean) and math.isnan(s.minimum))
        self.assertEqual((s.n, s.status, s.valid), (0, "missing", 0.0))
        self.assertEqual(s.reason, "INVALID, not connected")

    def test_updates_outside_the_window_are_clipped(self):
        s = summarize([(0.0, 1.0, None), (2.0, 5.0, None)], 0.0, 1.0)
        self.assertEqual(s.mean, 1.0)

    def test_a_dwell_of_zero(self):
        s = summarize([(3.0, 7.0, None)], 3.0, 3.0)
        self.assertEqual((s.mean, s.n, s.status), (7.0, 1, "ok"))


if __name__ == "__main__":
    unittest.main()
