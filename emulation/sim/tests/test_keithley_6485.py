"""keithley_6485: power-on state, trigger model, readings, ranges, overflow, timing."""

import unittest

import helpers  # noqa: F401  (sys.path, quiet logging)

from mist2sim.core import ConfigError, FakeClock, build

POLL = "ABOR;:SYST:ZCH?;:CURR:RANG?;:CURR:RANG:AUTO?;:CURR:NPLC?;:SENS:DATA?"


def make(**options):
    clock = FakeClock()
    sim = build({"name": "pico", "type": "keithley_6485", "port": 0, "options": options},
                clock=clock)
    return sim, clock


def ask(sim, line):
    lines = sim.process(line)
    return lines[0].decode() if lines else None


def poll(sim):
    """(zch, range, auto, nplc, reading text, timestamp, status) of one poll, then INIT."""
    reply = ask(sim, POLL)
    ask(sim, "INIT")
    zch, rng, auto, nplc, data = [x.strip() for x in reply.split(";")]
    reading, stamp, status = [x.strip() for x in data.split(",")]
    assert reading.endswith("A")
    return int(zch), float(rng), int(auto), float(nplc), reading[:-1], float(stamp), \
        int(float(status))


class PowerOn(unittest.TestCase):
    def test_factory_setup_measures_and_blocks_commands(self):
        sim, clock = make()
        clock.advance(1.0)
        self.assertIsNone(ask(sim, "*IDN?"))                 # 7-4: not executed while measuring
        self.assertIsNone(ask(sim, "SYST:ZCH?"))
        zch, rng, auto, nplc, reading, stamp, status = poll(sim)
        self.assertEqual((zch, rng, auto, nplc), (1, 2e-4, 1, 6.0))     # Table 1-3
        self.assertEqual(status, 0x200)                      # zero check, no measurement
        self.assertAlmostEqual(stamp, 0.9, places=6)         # three readings of 0.3 s done
        self.assertEqual(sim.signals["n_set"].value, 0)

    def test_rst_setup_is_idle_without_reading(self):
        sim, clock = make(power_on_setup="RST")
        self.assertEqual(ask(sim, "SYST:ZCH?"), "1")         # idle: executed
        # -230, no reading yet (3-5): the answers before it come, the rest is ignored (9-15)
        self.assertEqual(ask(sim, POLL), "1; 2.000000E-04; 1; 6.000000E+00")
        ask(sim, "INIT")
        clock.advance(0.31)
        self.assertEqual(poll(sim)[0], 1)

    def test_50_hz_and_identity(self):
        sim, clock = make(line_frequency=50)
        self.assertEqual(ask(sim, "ABOR;*IDN?"),
                         "KEITHLEY INSTRUMENTS INC., MODEL 6485, 0000000, SIM00/SIM00/A")
        self.assertEqual(ask(sim, "CURR:NPLC?"), "5.000000E+00")

    def test_power_cycle_returns_to_the_power_on_setup(self):
        sim, clock = make()
        ask(sim, "ABOR;:SYST:ZCH OFF;:CURR:RANG:AUTO OFF;:CURR:RANG 2E-9")
        sim.signals["power"].force(0)
        sim.step_couplings()
        self.assertIsNone(ask(sim, "ABOR;:SYST:ZCH?"))
        sim.signals["power"].force(1)
        sim.step_couplings()
        self.assertEqual(ask(sim, "ABOR;:SYST:ZCH?;:CURR:RANG:AUTO?"), "1; 1")

    def test_bad_options(self):
        for options in ({"power_on_setup": "X"}, {"line_frequency": 55},
                        {"power_on_range": 3e-4}):
            with self.assertRaises(ConfigError):
                make(**options)


class Measuring(unittest.TestCase):
    def setUp(self):
        self.sim, self.clock = make(current=1.234567891e-7)
        ask(self.sim, "ABOR;:SYST:ZCH OFF")
        ask(self.sim, "INIT")
        self.clock.advance(1.0)

    def test_reading_format_and_digits(self):
        reply = ask(self.sim, "ABOR;:SENS:DATA?")
        self.assertRegex(reply, r"^\+1\.234568E-07A, \+\d\.\d{6}E[-+]\d\d, \+0\.000000E\+00$")
        sim, clock = make(spaces=False)
        clock.advance(1)
        self.assertRegex(ask(sim, POLL), r"^1;2\.000000E-04;1;6\.000000E\+00;[^ ]+A,[^ ]+,[^ ]+$")

    def test_fixed_ranges_and_overflow(self):
        for r in (2e-9, 2e-8, 2e-7, 2e-6, 2e-5, 2e-4, 2e-3, 2e-2):
            ask(self.sim, "ABOR;:CURR:RANG:AUTO OFF;:CURR:RANG %g" % r)
            ask(self.sim, "INIT")
            self.sim.signals["current"].force(1.04 * r)
            self.clock.advance(0.5)
            self.assertEqual(poll(self.sim)[1:5], (r, 0, 6.0, "%+.6E" % (1.04 * r)))
            self.sim.signals["current"].force(-1.06 * r)     # beyond 5 % over range (4-2)
            self.clock.advance(0.5)
            reading, status = poll(self.sim)[4::2]
            self.assertEqual((reading, status), ("+9.9E37", 1))

    def test_autorange_up_at_105_percent_down_at_the_lower_range(self):
        cur = self.sim.signals["current"]
        for value, expected in ((1.5e-9, 2e-9), (2.09e-9, 2e-9), (2.2e-9, 2e-8),
                                (2.05e-9, 2e-8), (1.9e-9, 2e-9), (2.1e-6, 2e-6), (1.9e-8, 2e-8), (0.0211, 0.02)):
            cur.force(value)
            self.clock.advance(0.5)
            got = poll(self.sim)
            self.assertEqual(got[1], expected, value)
        self.assertEqual(got[6], 0x001)                      # 21.1 mA: overflow also in AUTO

    def test_set_commands_and_counters(self):
        self.assertEqual(ask(self.sim, "ABOR;:SYST:ZCH ON;:SYST:ZCH?"), "1")
        self.assertEqual(ask(self.sim, "ABOR;:CURR:RANG:AUTO OFF;:CURR:RANG 2E-6;"
                                       ":CURR:RANG:AUTO?"), "0")
        self.assertEqual(ask(self.sim, "ABOR;:SENS1:CURR:DC:RANG:UPP?;:SYSTEM:ZCHECK?"),
                         "2.000000E-06; 1")
        self.assertEqual(self.sim.signals["n_set"].value, 4)   # ZCH OFF in setUp + 3
        self.assertIsNone(ask(self.sim, "ABOR;:CURR:RANG 0.5;:CURR:RANG?"))   # out of range
        self.assertIsNone(ask(self.sim, "ABOR;:FOO 1;:SYST:ZCH?"))            # undefined header
        self.assertEqual(self.sim.signals["n_set"].value, 4)

    def test_reading_time_follows_nplc_and_autozero(self):
        ask(self.sim, "ABOR;:CURR:NPLC 1")
        self.assertAlmostEqual(self.sim.reading_time(), 1 / 60 * 3)
        ask(self.sim, "SYST:AZER OFF")
        self.assertAlmostEqual(self.sim.reading_time(), 1 / 60)
        ask(self.sim, "INIT")                               # at t = 1.0 s after power-on
        self.clock.advance(0.1)
        self.assertAlmostEqual(poll(self.sim)[5], 1.1, places=6)   # 6 readings of 1/60 s done

    def test_new_reading_only_after_a_reading_time(self):
        stamp = poll(self.sim)[5]
        self.clock.advance(0.2)                             # < 0.3 s: none completed
        self.assertEqual(poll(self.sim)[5], stamp)

    def test_zero_check_reading(self):
        ask(self.sim, "ABOR;:SYST:ZCH ON")
        ask(self.sim, "INIT")
        self.clock.advance(0.4)
        self.assertEqual(poll(self.sim)[4:7:2], ("+0.000000E+00", 0x200))


class Finite(unittest.TestCase):
    def test_finite_count_holds_the_answer_until_the_reading_is_done(self):
        sim, clock = make(power_on_setup="RST")
        ask(sim, "INIT")
        self.assertIsNone(ask(sim, "SYST:ZCH?"))             # waits for idle (7-4)
        self.assertAlmostEqual(sim.tick(sim.now()), 0.3)
        clock.advance(0.3)
        sim.tick(sim.now())
        self.assertEqual(sim.outbox, [b"1"])


if __name__ == "__main__":
    unittest.main()
