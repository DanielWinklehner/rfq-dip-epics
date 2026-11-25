"""edwards_tic: replies of D397-30-880 Issue H, variants, the cases of a missing gauge or pump."""

import unittest

import helpers  # noqa: F401  (sys.path, quiet logging)

from mist2sim.core import ConfigError, FakeClock, build

PA_PER_TORR = 101325.0 / 760.0


def make(**options):
    sim = build({"name": "tic", "type": "edwards_tic", "port": 0, "options": options},
                clock=FakeClock())
    return sim


def ask(sim, line):
    lines = sim.process(line)
    return lines[0].decode() if lines else None


def gauge(reply):
    head, _, data = reply.partition(" ")
    value, units, state, alert, prio = data.split(";")
    return head, float(value), int(units), int(state), int(alert), int(prio)


class Tic(unittest.TestCase):
    def setUp(self):
        self.sim = make(noise=0.0, gauges=[{"pressure": 1e-6}, {"pressure": 5e-3}, None])

    def test_gauge_reading_in_pascal(self):
        reply = ask(self.sim, "?V913")
        self.assertRegex(reply, r"^=V913 \d\.\d{4}e[-+]\d\d;59;11;0;0$")
        head, value, units, state, _, _ = gauge(reply)
        self.assertAlmostEqual(value / (1e-6 * PA_PER_TORR), 1.0, places=3)
        self.assertEqual((head, units, state), ("=V913", 59, 11))
        self.assertAlmostEqual(gauge(ask(self.sim, "?V914"))[1] / (5e-3 * PA_PER_TORR), 1, places=3)

    def test_socket_without_gauge(self):
        self.assertEqual(ask(self.sim, "?V915"), "=V915 9.9000e+09;59;0;0;0")

    def test_gauge_off_striking_alert_voltage(self):
        s = self.sim.signals
        for state in (5, 6, 4):
            s["g1.state"].force(state)
            self.assertEqual(gauge(ask(self.sim, "?V913"))[1:4], (9.9e9, 59, state))
        s["g1.state"].force(11)
        s["g1.units"].force(66)
        self.assertEqual(gauge(ask(self.sim, "?V913"))[1:4], (6.546, 66, 11))

    def test_pumps_and_types(self):
        self.assertEqual(ask(self.sim, "?V904"), "=V904 4;0;0")
        self.assertEqual(ask(self.sim, "?V905"), "=V905 100.0;0;0")
        self.assertEqual(ask(self.sim, "?V910"), "=V910 4;0;0")
        self.assertEqual(ask(self.sim, "?S904 3"), "=S904 3;11")
        self.assertEqual(ask(self.sim, "?S910 3"), "=S910 3;8")
        self.assertEqual(ask(self.sim, "?S904"), "*S904 3")
        self.assertEqual(ask(self.sim, "?S904 4"), "*S904 9")
        self.sim.signals["backing.type"].force(0)
        self.assertEqual(ask(self.sim, "?S910 3"), "=S910 3;0")
        self.sim.signals["turbo.absent"].force(1)
        self.assertEqual(ask(self.sim, "?V904"), "*V904 2")
        self.assertEqual(ask(self.sim, "?V905"), "*V905 2")
        self.assertEqual(ask(self.sim, "?S904 3"), "*S904 2")

    def test_identity_and_system_status(self):
        self.assertEqual(ask(self.sim, "?S902"), "=S902 TIC100;D39700640T;000000000\x00;5.0")
        self.assertEqual(ask(self.sim, "?V902"), "=V902 4;4;11;11;0;0;0;0;0;0")

    def test_variants(self):
        self.assertEqual(len(ask(make(variant="TC", gauges=[]), "?V902")[6:].split(";")), 7)
        ic = make(variant="IC")
        self.assertEqual(len(ask(ic, "?V902")[6:].split(";")), 8)
        self.assertEqual(ask(ic, "?V904"), "*V904 2")
        self.assertEqual(ask(ic, "?S910 3"), "*S910 2")
        self.assertEqual(len(ask(make(variant="IC6"), "?V902")[6:].split(";")), 14)
        self.assertTrue(ask(make(variant="IC6"), "?V936").startswith("=V936 9.9000e+09;59;0;"))
        self.assertEqual(ask(make(variant="TC", gauges=[]), "?V913"), "*V913 2")
        self.assertEqual(ask(make(variant="IC", absent_code=1), "?V904"), "*V904 1")

    def test_commands_are_counted_never_executed(self):
        self.assertEqual(ask(self.sim, "!C904 0"), "*C904 1")
        self.assertEqual(ask(self.sim, "!S929 2"), "*S929 1")
        self.assertEqual(self.sim.signals["commands"].value, 2)
        self.assertEqual(ask(self.sim, "?V904"), "=V904 4;0;0")
        self.assertEqual(self.sim.stats.heads, {"!": 2, "?": 1})

    def test_framing(self):
        self.assertTrue(ask(self.sim, "xx?V9?V913").startswith("=V913 "))   # 1.2
        self.assertIsNone(ask(self.sim, "V913"))
        self.assertEqual(ask(self.sim, "?V999"), "*V999 2")
        self.assertEqual(ask(self.sim, "?V913 1"), "*V913 2")

    def test_bad_configuration(self):
        with self.assertRaises(ConfigError):
            make(variant="TPG")
        with self.assertRaises(ConfigError):
            make(variant="TC", gauges=[{"pressure": 1e-6}])
        with self.assertRaises(ConfigError):
            make(gauges=[{"pressur": 1e-6}])


if __name__ == "__main__":
    unittest.main()
