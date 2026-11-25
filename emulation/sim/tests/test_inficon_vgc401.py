"""inficon_vgc401: ACK/ENQ dialogue, status digits, units, error word, the automatic
transmission after power-on, the framing of <ENQ> (manual tinb01e1-f, chapter 5)."""

import re
import unittest

from helpers import LineClient, wait_until

from mist2sim.control import ControlClient
from mist2sim.core import ConfigError, FakeClock, SimThread, build

ENQ = b"\x05"


def make(**options):
    options.setdefault("noise", 0.0)
    clock = FakeClock()
    sim = build({"name": "vgc", "type": "inficon_vgc401", "port": 0, "control_port": 0,
                 "options": options}, clock=clock)
    return sim, clock


def one(sim, request):
    lines = sim.process(request)
    return lines[0].decode("latin-1") if lines else None


def read(sim, mnemonic):
    """The manual's dialogue (p. 57): mnemonic -> <ACK>, <ENQ> -> data."""
    assert one(sim, mnemonic) == "\x06", mnemonic
    return one(sim, ENQ)


class Dialogue(unittest.TestCase):
    def setUp(self):
        self.sim, self.clock = make(unit=1, pressure=8.34e-3)

    def test_pr1_as_in_the_example_of_p75(self):
        self.assertEqual(read(self.sim, b"PR1"), "0, 8.3400E-03")
        self.assertEqual(one(self.sim, ENQ), "0, 8.3400E-03")        # repeated <ENQ>: again

    def test_value_format_and_two_decimals(self):
        self.sim.pressure.target = 1.23456e-2
        self.assertRegex(read(self.sim, b"PR1"), r"^0, \d\.\d\d00E[-+]\d\d$")    # p. 60 note

    def test_cdg_keeps_four_decimals(self):
        sim, _ = make(gauge="CDG", unit=1, pressure=1.23456e-2)
        self.assertEqual(read(sim, b"PR1"), "0, 1.2346E-02")

    def test_units(self):
        for unit, factor in ((0, 1.33322368), (1, 1.0), (2, 133.322368), (3, 1000.0)):
            self.sim.unit.target = unit
            self.assertEqual(read(self.sim, b"UNI"), str(unit))
            value = float(read(self.sim, b"PR1").split(",")[1])
            self.assertAlmostEqual(value / (8.34e-3 * factor), 1.0, delta=0.01)

    def test_default_unit_is_mbar(self):
        sim, _ = make()
        self.assertEqual(read(sim, b"UNI"), "0")                   # p. 82

    def test_status_digits_and_gauge(self):
        for status in range(8):
            self.sim.status.target = status
            self.assertTrue(read(self.sim, b"PR1").startswith("%d," % status))
        self.sim.status.target = 5
        self.assertEqual(read(self.sim, b"TID"), "noSEn")
        self.sim.status.target = 6
        self.assertEqual(read(self.sim, b"TID"), "noid")
        self.sim.status.target = 0
        self.assertEqual(read(self.sim, b"TID"), "PSG")

    def test_firmware(self):
        self.assertEqual(read(self.sim, b"PNR"), "302-519-E")

    def test_unknown_mnemonic_as_in_p75(self):
        self.assertEqual(one(self.sim, b"FOL,2"), "\x15")
        self.assertEqual(one(self.sim, ENQ), "0001")
        self.assertEqual(read(self.sim, b"ERR"), "0000")          # cancelled when read out
        self.assertEqual(self.sim.signals["n_nak"].value, 1)

    def test_enq_without_request_gives_the_error_word(self):
        self.assertEqual(one(self.sim, ENQ), "0000")

    def test_controller_error_persists(self):
        self.sim.controller_error.target = 1
        self.assertEqual(read(self.sim, b"ERR"), "1000")
        self.assertEqual(read(self.sim, b"ERR"), "1000")
        self.sim.controller_error.target = 0
        self.assertEqual(read(self.sim, b"ERR"), "0000")

    def test_reads_do_not_count_as_sets(self):
        for m in (b"PR1", b"UNI", b"TID", b"ERR", b"PNR"):
            read(self.sim, m)
        self.assertEqual(self.sim.signals["n_set"].value, 0)
        self.assertEqual(self.sim.signals["n_enq"].value, 5)

    def test_parameter_is_a_set(self):
        self.assertEqual(one(self.sim, b"UNI,2"), "\x06")
        self.assertEqual(self.sim.signals["n_set"].value, 1)
        self.assertEqual(one(self.sim, ENQ), "2")
        self.assertEqual(one(self.sim, b"UNI,7"), "\x15")
        self.assertEqual(read(self.sim, b"ERR"), "0010")
        self.assertEqual(one(self.sim, b"SP1,1E-3,2E-3"), "\x06")   # counted, not applied
        self.assertEqual(self.sim.signals["n_set"].value, 3)

    def test_spaces_are_ignored(self):
        self.assertEqual(one(self.sim, b" P R1 "), "\x06")

    def test_refuse_uni(self):
        self.sim.refuse_uni.target = 1
        self.assertEqual(one(self.sim, b"UNI"), "\x15")

    def test_power_off_is_silent(self):
        self.sim.power.target = 0
        self.assertIsNone(one(self.sim, b"PR1"))

    def test_bad_options(self):
        for options in ({"gauge": "XYZ"}, {"unit": 4}, {"com_mode": 3}):
            with self.assertRaises(ConfigError):
                make(**options)


class Framing(unittest.TestCase):
    def test_split(self):
        split = build({"name": "v", "type": "inficon_vgc401", "port": 0}).split
        self.assertEqual(split(b"PR1\r"), ([b"PR1"], b""))
        self.assertEqual(split(b"PR1\r\n\x05UN"), ([b"PR1", b"\x05"], b"UN"))
        self.assertEqual(split(b"PR1\n"), ([b"PR1"], b""))
        self.assertEqual(split(b"XX\x03PR1\r"), ([b"PR1"], b""))      # <ETX> clears


class Automatic(unittest.TestCase):
    def test_tick_sends_once_per_second(self):
        sim, _ = make(unit=1, pressure=7.5e-3)
        sim.tick(0.0)
        self.assertEqual(sim.outbox, [b"0, 7.5000E-03 Torr"])
        sim.tick(0.5)
        self.assertEqual(len(sim.outbox), 1)
        sim.tick(1.0)
        self.assertEqual(len(sim.outbox), 2)

    def test_not_configured(self):
        sim, _ = make(continuous=False)
        sim.tick(0.0)
        self.assertEqual(sim.outbox, [])

    def test_power_cycle_starts_it_again(self):
        sim, clock = make()
        sim.continuous.target = 0
        sim.power.target = 0
        sim.step_couplings()
        sim.power.target = 1
        clock.advance(1.0)
        sim.step_couplings()
        self.assertEqual(sim.continuous.value, 1.0)


class Tcp(unittest.TestCase):
    def test_listen_then_ask(self):
        sim = build({"name": "vgc", "type": "inficon_vgc401", "port": 0, "control_port": 0,
                     "baud": 38400, "options": {"unit": 1, "pressure": 7.5e-3, "noise": 0.0}})
        with SimThread([sim]):
            c = LineClient(sim.port, term=b"\r\n")
            self.addCleanup(c.close)
            self.assertEqual(c.readline(1.5), b"0, 7.5000E-03 Torr")   # sends by itself
            c.send(b"PR1\r")                                           # ... until asked
            line = c.readline(1.0)
            if line != b"\x06":                                        # one on its way
                self.assertEqual(line, b"0, 7.5000E-03 Torr")
                self.assertEqual(c.readline(1.0), b"\x06")
            c.send(ENQ)                                                # no terminator
            self.assertEqual(c.readline(1.0), b"0, 7.5000E-03")
            self.assertIsNone(c.readline(1.5))                         # nothing by itself
            with ControlClient("127.0.0.1", sim.control_port) as ctl:
                self.assertEqual(ctl.get("continuous")["value"], 0.0)
                self.assertEqual(ctl.get("n_set")["value"], 0.0)
                ctl.set("status", 3)
                c.send(b"PR1\r\n")                                     # CR LF ends it too
                self.assertEqual(c.readline(1.0), b"\x06")
                c.send(ENQ)
                self.assertTrue(re.match(rb"^3,", c.readline(1.0)))
                ctl.fault("silent")
                c.send(b"PR1\r")
                self.assertIsNone(c.readline(0.5))
                ctl.clear()
                c.send(b"PR1\r")
                self.assertTrue(wait_until(lambda: c.readline(0.2) == b"\x06", 2.0))


if __name__ == "__main__":
    unittest.main()
