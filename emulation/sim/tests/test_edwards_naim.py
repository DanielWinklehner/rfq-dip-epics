"""edwards_naim: Edwards message format, object 752, gauge on/off, drift."""

import unittest

import helpers  # noqa: F401  (sys.path, quiet logging)

from mist2sim.core import ConfigError, FakeClock, build


def make(**options):
    clock = FakeClock()
    sim = build({"name": "aim", "type": "edwards_naim", "port": 0, "options": options}, clock=clock)
    return sim, clock


def ask(sim, line):
    lines = sim.process(line)
    return lines[0].decode() if lines else None


def parse(reply):
    head, _, data = reply.partition(" ")
    pressure, status = data.split(";")
    return head, float(pressure), int(status, 16)


class Naim(unittest.TestCase):
    def setUp(self):
        self.sim, self.clock = make(noise=0.0)

    def test_pressure_and_status(self):
        head, p, status = parse(ask(self.sim, "?V752"))
        self.assertEqual(head, "=V752")
        self.assertAlmostEqual(p / 1e-6, 1.0, places=2)
        self.assertEqual(status, 0x0032)                     # on, torr
        self.assertRegex(ask(self.sim, "?V752"), r"^=V752 \d\.\d\dE[-+]\d\d;[0-9A-F]{4}$")

    def test_switch_off_and_on(self):
        self.assertEqual(ask(self.sim, "!C752 0"), "*C752 0")
        _, p, status = parse(ask(self.sim, "?V752"))
        self.assertEqual((p, status), (9.9e9, 0x0030))
        self.assertEqual(ask(self.sim, "!C752 1"), "*C752 0")
        _, p, status = parse(ask(self.sim, "?V752"))
        self.assertEqual((p, status), (9.9e9, 0x0132))       # striking
        self.clock.advance(2.5)
        _, p, status = parse(ask(self.sim, "?V752"))
        self.assertEqual(status, 0x0032)
        self.assertLess(p, 1e-5)

    def test_error_replies(self):
        self.assertEqual(ask(self.sim, "!C752"), "*C752 3")
        self.assertEqual(ask(self.sim, "!C752 7"), "*C752 4")
        self.assertEqual(ask(self.sim, "?V999"), "*V999 2")
        self.assertEqual(ask(self.sim, "!C999 1"), "*C999 2")
        self.assertEqual(ask(self.sim, "?S755"), "*S755 1")
        self.assertIsNone(ask(self.sim, "V752"))             # no start character
        self.sim.signals["reject"].force(5)
        self.assertEqual(ask(self.sim, "!C752 0"), "*C752 5")
        self.assertEqual(self.sim.signals["on"].value, 1.0)  # not executed

    def test_noise_before_the_start_character_is_ignored(self):
        self.assertTrue(ask(self.sim, "xx?V7?V752").startswith("=V752 "))

    def test_units_and_error_bit(self):
        self.assertEqual(ask(self.sim, "!S755 2"), "*S755 0")
        _, p, status = parse(ask(self.sim, "?V752"))
        self.assertEqual(status & 0x30, 0x20)
        self.assertAlmostEqual(p / 1.33e-4, 1.0, places=1)    # pascal
        self.sim.signals["error"].force(1)
        self.assertEqual(parse(ask(self.sim, "?V752"))[2] & 1, 1)

    def test_pressure_follows_the_plant_and_drifts_without_it(self):
        self.sim.signals["pressure"].force(3e-7)
        self.clock.advance(100)
        self.assertAlmostEqual(parse(ask(self.sim, "?V752"))[1], 3e-7)
        self.sim.signals["pressure"].release()
        seen = set()
        for _ in range(50):
            self.clock.advance(10)
            seen.add(parse(ask(self.sim, "?V752"))[1])
        self.assertGreater(len(seen), 10)
        self.assertTrue(all(1e-7 < p < 1e-5 for p in seen))

    def test_multidrop(self):
        sim, _ = make(address=5)
        self.assertIsNone(ask(sim, "?V752"))
        self.assertTrue(ask(sim, "#05:01?V752").startswith("#01:05=V752 "))
        self.assertIsNone(ask(sim, "#04:01?V752"))
        self.assertIsNone(ask(sim, "#00:01!C752 0"))
        self.assertEqual(sim.signals["on"].value, 0.0)

    def test_bad_units_option(self):
        with self.assertRaises(ConfigError):
            make(units="psi")


if __name__ == "__main__":
    unittest.main()
