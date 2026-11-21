"""matsusada_co: the CO series command set and the supply model, without an IOC."""

import time
import unittest

from helpers import LineClient

from mist2sim.control import ControlClient, ControlError
from mist2sim.core import ConfigError, FakeClock, SimThread, build
from mist2sim.devices.matsusada_co import format_percent, parse, parse_percent

AU = {"vfs": 20000, "ifs": 0.0075}


def chain(units=None, clock=None, **options):
    if units is None:
        units = [dict(AU, address=1, load_ohm=4e6), dict(AU, address=2, polarity="-")]
    options["units"] = units
    options.setdefault("noise", 0.0)
    return build({"name": "chain", "type": "matsusada_co", "port": 0, "options": options},
                 clock=clock or FakeClock())


def remote(sim, *units):
    for u in units:
        sim.process("#%d REN" % u)


class Parsing(unittest.TestCase):
    def test_syntax(self):
        self.assertEqual(parse(b"#1 CH0 FFFF"), (1, "CH0", "FFFF"))
        self.assertEqual(parse(b"#1ch0ffff"), (1, "CH0", "FFFF"))           # case, no spaces
        self.assertEqual(parse(b"# 12  CH0  F0"), (12, "CH0", "F0"))
        self.assertEqual(parse(b"#al sw1"), ("AL", "SW", "1"))
        self.assertEqual(parse(b"#3 PLM"), (3, "PLM", ""))
        self.assertEqual(parse(b"#3 PL1"), (3, "PL", "1"))
        self.assertEqual(parse(b"#3 CH1?"), (3, "CH1?", ""))
        for bad in (b"CH0 FFFF", b"#1 XYZ", b"#X STS", b"", b"#1 ST\x01S", b"\xff"):
            self.assertIsNone(parse(bad), bad)

    def test_percent(self):
        self.assertEqual(parse_percent("100"), 100.0)
        self.assertEqual(parse_percent("12.34"), 12.34)
        self.assertEqual(parse_percent("12.345"), 12.34)                     # manual: same as 12.34
        self.assertIsNone(parse_percent("123.4"))                            # manual: not changed
        self.assertIsNone(parse_percent("1000"))
        self.assertIsNone(parse_percent(""))
        self.assertEqual(format_percent(0xFFFF), "100.0")
        self.assertEqual(format_percent(0x7FFF), "50.0")
        self.assertEqual(format_percent(0), "0.0")


class Commands(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.sim = chain(clock=self.clock)

    def ask(self, line):
        return [x.decode() for x in self.sim.process(line)]

    def test_nothing_before_remote(self):
        self.assertEqual(self.ask("#1 STS"), [])
        self.assertEqual(self.ask("#1 CH0 FFFF"), [])
        self.assertEqual(self.ask("#1 REN"), [])
        self.assertEqual(self.ask("#1 CH0?"), ["CH0=0000H"])                # the set was ignored
        self.assertEqual(self.ask("#1 STS"), ["#1 CF RM"])
        self.assertEqual(self.ask("#1 GTL"), [])
        self.assertEqual(self.ask("#1 STS"), [])

    def test_queries_without_remote_setting(self):
        sim = chain(queries_without_remote=True)
        self.assertEqual(sim.process("#1 STS"), [b"#1 CF LO"])
        sim.process("#1 CH0 FFFF")
        self.assertEqual(sim.process("#1 CH0?"), [b"CH0=0000H"])          # sets still need REN

    def test_settings_and_replies(self):
        remote(self.sim, 1)
        for line in ("#1 CH0 7FFF", "#1 CH1 F0", "#1 SW1", "#1 PL1"):
            self.assertEqual(self.ask(line), [], line)                     # sets: no reply
        self.assertEqual(self.ask("#1 CH0?"), ["CH0=7FFFH"])
        self.assertEqual(self.ask("#1 CH1?"), ["CH1=00F0H"])
        self.assertEqual(self.ask("#1 VCN?"), ["VCN=50.0"])
        self.assertEqual(self.ask("#1 SW?"), ["SW1"])
        self.assertEqual(self.ask("#1 PL?"), ["PL1"])
        self.assertEqual(self.ask("#1 PLM"), ["PLM=0"])                     # hardware polarity
        self.assertEqual(self.ask("#1 STS"), ["#1 CO RM"])
        self.assertEqual(self.ask("#1 SRQ?"), [])

    def test_out_of_range_ignored(self):
        remote(self.sim, 1)
        self.sim.process("#1 CH0 1234")
        for line in ("#1 CH0 12345", "#1 CH0 XYZ", "#1 CH0", "#1 VCN 123.4", "#1 VCN 1000",
                     "#1 SW2", "#1 RST 1", "#1 REN 1", "#1 MN1 2"):
            self.assertEqual(self.ask(line), [], line)
        self.assertEqual(self.ask("#1 CH0?"), ["CH0=1234H"])
        self.sim.process("#1 VCN 12.345")
        self.assertEqual(self.ask("#1 VCN?"), ["VCN=12.34"])
        self.assertEqual(self.ask("#1 CH0?"), ["CH0=%04XH" % round(0.1234 * 0xFFFF)])

    def test_unknown_unit_and_wrong_command_get_no_reply(self):
        remote(self.sim, 1)
        self.assertEqual(self.ask("#7 STS"), [])
        self.assertEqual(self.ask("#1 HELLO"), [])
        self.assertEqual(self.ask("STS"), [])

    def test_icn_and_ch1_are_one_setting(self):
        remote(self.sim, 1)
        self.sim.process("#1 CH1 1000")
        self.sim.process("#1 ICN 100")
        self.assertEqual(self.ask("#1 CH1?"), ["CH1=FFFFH"])
        self.assertEqual(self.ask("#1 ICN?"), ["ICN=100.0"])
        sim = chain(icn_sets_ch1=False)
        remote(sim, 1)
        sim.process("#1 CH1 1000")
        sim.process("#1 ICN 50")
        self.assertEqual(sim.process("#1 CH1?"), [b"CH1=1000H"])
        self.assertEqual(sim.process("#1 ICN?"), [b"ICN=50.0"])
        self.assertAlmostEqual(sim.signals["1.iset"].value, 0.00375, places=6)      # the last one wins

    def test_multiple_command(self):
        remote(self.sim, 1)
        self.assertEqual(self.ask("#AL REN"), [])
        self.assertEqual(self.ask("#AL CH0 FFFF"), [])
        self.assertEqual(self.ask("#AL SW1"), [])
        self.assertEqual(self.ask("#1 SW?") + self.ask("#2 SW?"), ["SW1", "SW1"])
        self.assertEqual(self.ask("#2 CH0?"), ["CH0=FFFFH"])
        for line in ("#AL STS", "#AL SW?", "#AL MN1", "#AL CH0?"):
            self.assertEqual(self.ask(line), [], line)                     # not multiple commands
        self.ask("#AL SW0")
        self.assertEqual(self.ask("#1 STS") + self.ask("#2 STS"), ["#1 CF RM", "#2 CF RM"])

    def test_monitors_follow_with_time_constant(self):
        remote(self.sim, 1)
        self.sim.process("#1 CH0 FFFF")
        self.sim.process("#1 CH1 FFFF")
        self.assertEqual(self.ask("#1 MN1"), ["MONI1=000H"])                # output off
        self.sim.process("#1 SW1")
        self.clock.advance(0.3)                                             # one tau
        v = int(self.ask("#1 MN1")[0][6:9], 16)
        self.assertAlmostEqual(v / 0xFFF, 1 - 2.718281828 ** -1, delta=0.01)
        self.clock.advance(5)
        self.assertEqual(self.ask("#1 MN1"), ["MONI1=FFFH"])
        self.assertEqual(self.ask("#1 VM"), ["VM=100.0"])
        # 20 kV on 4 MOhm = 5 mA of 7.5 mA
        self.assertEqual(self.ask("#1 MN2"), ["MONI2=%03XH" % round(5 / 7.5 * 0xFFF)])
        self.sim.process("#1 SW0")
        self.clock.advance(5)
        self.assertEqual(self.ask("#1 MN1"), ["MONI1=000H"])
        self.assertEqual(self.ask("#1 MN2"), ["MONI2=000H"])

    def test_current_limit_pulls_the_voltage_down(self):
        remote(self.sim, 1)
        self.sim.process("#1 CH0 FFFF")
        self.sim.process("#1 CH1 %04X" % round(2.5 / 7.5 * 0xFFFF))         # 2.5 mA limit
        self.sim.process("#1 SW1")
        self.clock.advance(10)
        self.sim.step_couplings()
        self.assertAlmostEqual(self.sim.signals["1.iout"].value, 0.0025, places=6)
        self.assertAlmostEqual(self.sim.signals["1.vout"].value, 10000, delta=1)  # 2.5 mA x 4 MOhm

    def test_noise_and_12_bit(self):
        sim = chain(noise=0.001, units=[dict(AU, address=1, output_on=True, vset=10000)])
        codes = {int(sim.process("#1 MN1")[0][6:9], 16) for _ in range(200)}
        self.assertGreater(len(codes), 3)
        self.assertTrue(all(abs(c - 2048) < 30 for c in codes), codes)

    def test_trip_latches_until_rst(self):
        remote(self.sim, 1)
        self.sim.process("#1 CH0 FFFF")
        self.sim.process("#1 SW1")
        self.sim.add_fault("trip", 1)
        self.assertEqual(self.ask("#1 STS"), ["#1 CF RM"])                  # cut off ...
        self.assertEqual(self.ask("#1 SW?"), ["SW1"])                       # ... with SW1 set
        self.clock.advance(5)
        self.assertEqual(self.ask("#1 MN1"), ["MONI1=000H"])
        self.sim.clear_faults()
        self.assertEqual(self.ask("#1 STS"), ["#1 CF RM"])                  # still off
        self.sim.process("#1 RST")
        self.assertEqual(self.ask("#1 STS"), ["#1 CO RM"])

    def test_trip_on_every_unit(self):
        self.sim = chain(units=[dict(AU, address=1, output_on=True), dict(AU, address=2,
                                                                          output_on=True)])
        self.sim.add_fault("trip")
        self.assertEqual(self.ask("#1 STS") + self.ask("#2 STS"), ["#1 CF RM", "#2 CF RM"])
        self.sim.process("#AL RST")
        self.assertEqual(self.ask("#1 STS") + self.ask("#2 STS"), ["#1 CO RM", "#2 CO RM"])

    def test_bang_when_off(self):
        sim = chain(bang_when_off=True, units=[dict(AU, address=1, output_on=True)])
        sim.process("#1 SW0")
        self.assertEqual(sim.outbox, [b"!"])
        sim.process("#1 SW0")
        self.assertEqual(sim.outbox, [b"!"])                                 # only on a change
        self.assertEqual(self.sim.outbox, [])                                # default: off

    def test_srq_query_setting(self):
        self.assertEqual(chain(srq_query_reply=True).process("SRQ?"), [b"SRQ OFF"])
        self.assertEqual(chain().process("SRQ?"), [])

    def test_start_state(self):
        sim = chain(units=[dict(AU, address=4, output_on=True, vset=5000, iset=0.0075)])
        self.assertEqual(sim.process("#4 STS"), [b"#4 CO RM"])
        self.assertEqual(sim.process("#4 MN1"), [b"MONI1=%03XH" % round(0.25 * 0xFFF)])

    def test_signals_for_a_plant_model(self):
        remote(self.sim, 1)
        self.sim.process("#1 CH0 FFFF")
        self.sim.signals["1.vout"].force(1234.0)
        self.assertEqual(self.ask("#1 MN1"), ["MONI1=%03XH" % round(1234 / 20000 * 0xFFF)])
        for name in ("vset", "iset", "vout", "iout", "output", "sw", "cutoff", "remote",
                     "load_ohm"):
            self.assertIn("2.%s" % name, self.sim.signals)

    def test_configuration_errors(self):
        for units in ([], [{"address": 1}], [dict(AU, address=40)], [dict(AU, address=1, x=1)],
                      [dict(AU, address=1, polarity="n")], [dict(AU, address=1, vfs=0)]):
            with self.assertRaises(ConfigError):
                chain(units=units)


class OverTheLine(unittest.TestCase):
    """Real sockets: delimiters, line timing, faults, the control interface."""

    def setUp(self):
        self.sim = chain(units=[dict(AU, address=1, output_on=True, vset=20000, iset=0.0075),
                                dict(AU, address=2, output_on=True)])

    def test_cr_and_lf_delimiters_and_timing(self):
        with SimThread([self.sim]):
            c = LineClient(self.sim.port, term=b"\r")
            c.send(b"#1 STS\r")
            self.assertEqual(c.readline(1), b"#1 CO RM")
            c.send(b"#1 sw?\n")
            self.assertEqual(c.readline(1), b"SW1")
            t = time.monotonic()
            c.send(b"#1 MN1\r")
            self.assertEqual(c.readline(1)[:6], b"MONI1=")
            # 7 + 11 characters at 9600 baud = 18.75 ms, plus 5 ms turnaround
            self.assertGreater(time.monotonic() - t, 0.0235)
            c.close()

    def test_back_to_back_transactions_keep_the_line_timing(self):
        """A full line: each reply comes at its computed time, not up to 1 ms later."""
        with SimThread([self.sim]):
            c = LineClient(self.sim.port, term=b"\r")
            c.send(b"#1 MN1\r")
            c.readline(1)
            n, t0 = 50, time.monotonic()
            for _ in range(n):
                c.send(b"#1 MN1\r")
                self.assertIsNotNone(c.readline(1))
            per = (time.monotonic() - t0) / n
            self.assertLess(per, 0.02375 + 0.0005)        # 18 characters + 5 ms turnaround
            c.close()

    def test_silent_unit_and_turnaround_knob(self):
        with SimThread([self.sim]):
            c = LineClient(self.sim.port, term=b"\r")
            with ControlClient("127.0.0.1", self.sim.control_port) as ctl:
                ctl.fault("silent", unit=1)
                c.send(b"#1 STS\r")
                self.assertIsNone(c.readline(0.2))
                c.send(b"#2 STS\r")
                self.assertEqual(c.readline(1), b"#2 CO RM")
                ctl.clear()
                ctl.set("line.turnaround_ms", 100)
                t = time.monotonic()
                c.send(b"#1 STS\r")
                self.assertEqual(c.readline(1), b"#1 CO RM")
                self.assertGreater(time.monotonic() - t, 0.1)
                ctl.fault("trip", unit=2)
                self.assertEqual(ctl.get("2.output")["value"], 0.0)
                self.assertEqual(ctl.stats()["per_unit"]["1"]["replies"], 1)
                with self.assertRaises(ControlError):
                    ctl.fault("close", unit=1)
            c.close()


if __name__ == "__main__":
    unittest.main()
