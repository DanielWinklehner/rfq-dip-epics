"""tdk_genesys: protocol of the GENESYS manual chapter 7 and the output model."""

import unittest

import helpers  # noqa: F401  (sys.path, quiet logging)

from mist2sim.control import ControlClient
from mist2sim.core import FakeClock, SimThread, build


def make(**options):
    clock = FakeClock()
    sim = build({"name": "tdk", "type": "tdk_genesys", "port": 0, "options": options}, clock=clock)
    return sim, clock


def ask(sim, line):
    lines = sim.process(line)
    return lines[0].decode() if lines else None


class Protocol(unittest.TestCase):
    def setUp(self):
        self.sim, self.clock = make(noise_v=0.0, noise_i=0.0)

    def test_unaddressed_supply_is_silent_until_adr(self):
        self.assertIsNone(ask(self.sim, "IDN?"))
        self.assertIsNone(ask(self.sim, "ADR 5"))          # someone else's address
        self.assertIsNone(ask(self.sim, "OUT 1"))
        self.assertEqual(ask(self.sim, "ADR 06"), "OK")
        self.assertEqual(ask(self.sim, "IDN?"), "LAMBDA,GEN8-300")
        self.assertIsNone(ask(self.sim, "ADR 7"))          # deselected again
        self.assertIsNone(ask(self.sim, "IDN?"))

    def test_line_rules(self):
        ask(self.sim, "ADR 6")
        self.assertEqual(ask(self.sim, ""), "OK")            # a CR by itself
        self.assertEqual(ask(self.sim, "idn?\n"), "LAMBDA,GEN8-300")   # LF ignored, any case
        self.assertEqual(ask(self.sim, "IDX\b\bDN?"), "LAMBDA,GEN8-300")   # backspace
        self.assertEqual(ask(self.sim, "PV 1.5"), "OK")
        self.assertEqual(ask(self.sim, "PV?"), "1.5")
        self.assertEqual(ask(self.sim, "\\"), "1.5")         # repeat the last command

    def test_checksum(self):
        ask(self.sim, "ADR 6")
        self.assertEqual(ask(self.sim, "OUT?$" + "%02X" % (sum(b"OUT?") % 256)),
                         "OFF$" + "%02X" % (sum(b"OFF") % 256))
        self.assertEqual(ask(self.sim, "STT?$3A")[:3], "MV(")   # the example of 7.5.5
        self.assertEqual(ask(self.sim, "OUT?$00"), "C04$" + "%02X" % (sum(b"C04") % 256))

    def test_errors(self):
        ask(self.sim, "ADR 6")
        self.assertEqual(ask(self.sim, "XYZ"), "C01")
        self.assertEqual(ask(self.sim, "IDN? 1"), "C01")
        self.assertEqual(ask(self.sim, "PV"), "C02")
        self.assertEqual(ask(self.sim, "PV abc"), "C03")
        self.assertEqual(ask(self.sim, "PV 1.0000000000000"), "C03")   # more than 12 chars
        self.assertEqual(ask(self.sim, "PV 8.5"), "E01")      # above 105 % of 8 V
        self.assertEqual(ask(self.sim, "OVP 5"), "OK")
        self.assertEqual(ask(self.sim, "PV 4.9"), "E01")      # above 95 % of OVP
        self.assertEqual(ask(self.sim, "PV 2"), "OK")
        self.assertEqual(ask(self.sim, "OVP 2.05"), "E04")    # below 105 % of PV
        self.assertEqual(ask(self.sim, "UVL 3"), "E06")
        self.assertEqual(ask(self.sim, "UVL 1"), "OK")
        self.assertEqual(ask(self.sim, "PV 0.5"), "E02")
        self.assertEqual(ask(self.sim, "PC 316"), "C05")
        self.assertEqual(ask(self.sim, "OUT 2"), "C03")
        self.assertEqual(ask(self.sim, "PV?"), "2")           # rejected sets changed nothing

    def test_identity_and_registers(self):
        ask(self.sim, "ADR 6")
        self.assertEqual(ask(self.sim, "RMT?"), "LOC")
        self.assertEqual(ask(self.sim, "STAT?"), "84")        # local, no fault
        ask(self.sim, "PV 1")
        self.assertEqual(ask(self.sim, "RMT?"), "REM")        # a set puts it into remote
        self.assertEqual(ask(self.sim, "FLT?"), "00")
        self.assertEqual(ask(self.sim, "FENA FF"), "OK")
        self.assertEqual(ask(self.sim, "FENA?"), "FF")
        self.sim.signals["enable_open"].force(1)
        self.assertEqual(ask(self.sim, "FLT?"), "80")
        self.assertEqual(ask(self.sim, "STAT?"), "08")        # FLT, no NFLT
        self.assertEqual(ask(self.sim, "FEVE?"), "80")
        self.sim.signals["enable_open"].force(0)
        self.assertEqual(ask(self.sim, "FEVE?"), "00")        # cleared by reading
        self.assertEqual(ask(self.sim, "SENA 03"), "OK")
        ask(self.sim, "PC 300")
        ask(self.sim, "OUT 1")
        self.clock.advance(2.0)
        self.assertEqual(ask(self.sim, "SEVE?"), "01")        # CV came up
        self.assertEqual(ask(self.sim, "SEVE?"), "00")
        self.assertTrue(ask(self.sim, "STT?").startswith(
            "MV(1.000),PV(1),MC(040.00),PC(300),SR(05)"))


class Model(unittest.TestCase):
    def setUp(self):
        self.sim, self.clock = make(noise_v=0.0, noise_i=0.0, load_ohm=0.025, tau_s=0.1)
        ask(self.sim, "ADR 6")

    def settle(self):
        self.clock.advance(2.0)

    def test_constant_voltage_and_constant_current(self):
        self.assertEqual(ask(self.sim, "MODE?"), "OFF")
        ask(self.sim, "PV 2")
        ask(self.sim, "PC 300")
        ask(self.sim, "OUT 1")
        self.clock.advance(0.1)
        self.assertLess(float(ask(self.sim, "MV?")), 1.5)      # still rising
        self.settle()
        self.assertEqual((ask(self.sim, "MODE?"), ask(self.sim, "MV?"), ask(self.sim, "MC?")),
                         ("CV", "2.000", "080.00"))
        ask(self.sim, "PV 8")
        ask(self.sim, "PC 100")
        self.settle()
        self.assertEqual((ask(self.sim, "MODE?"), ask(self.sim, "MV?"), ask(self.sim, "MC?")),
                         ("CC", "2.500", "100.00"))
        self.sim.signals["load_ohm"].force(0.01)               # the plant changes the load
        self.sim.step_couplings()                              # (the next request does that)
        self.settle()
        self.assertEqual(ask(self.sim, "MV?"), "1.000")
        ask(self.sim, "OUT 0")
        self.settle()
        self.assertEqual((ask(self.sim, "OUT?"), ask(self.sim, "MODE?"), ask(self.sim, "MC?")),
                         ("OFF", "OFF", "000.00"))

    def test_trip_is_an_ovp_shutdown_cleared_by_out_1(self):
        ask(self.sim, "PV 2")
        ask(self.sim, "PC 300")
        ask(self.sim, "OUT 1")
        self.sim.add_fault("trip")
        self.assertEqual((ask(self.sim, "OUT?"), ask(self.sim, "FLT?")), ("OFF", "10"))
        self.sim.clear_faults("trip")
        self.assertEqual(ask(self.sim, "FLT?"), "10")           # latched in the supply
        self.assertEqual(ask(self.sim, "OUT 1"), "OK")
        self.assertEqual((ask(self.sim, "OUT?"), ask(self.sim, "FLT?")), ("ON", "00"))

    def test_enable_open_is_a_latching_shutdown(self):
        ask(self.sim, "OUT 1")
        self.sim.signals["enable_open"].force(1)
        self.assertEqual(ask(self.sim, "OUT?"), "OFF")
        self.assertEqual(ask(self.sim, "OUT 1"), "E07")
        self.sim.signals["enable_open"].release()
        self.sim.signals["enable_open"].target = 0
        self.assertEqual(ask(self.sim, "OUT?"), "OFF")          # safe start: needs OUT 1
        self.assertEqual(ask(self.sim, "OUT 1"), "OK")
        self.assertEqual(ask(self.sim, "OUT?"), "ON")

    def test_power_cycle_forgets_the_address_and_keeps_the_settings(self):
        ask(self.sim, "PV 2")
        ask(self.sim, "PC 50")
        ask(self.sim, "OUT 1")
        self.sim.add_fault("trip")
        self.sim.signals["ac_power"].force(0)
        self.assertIsNone(ask(self.sim, "ADR 6"))               # dead
        self.sim.signals["ac_power"].release()                  # back on
        self.assertIsNone(ask(self.sim, "OUT?"))                # unaddressed
        self.assertEqual(ask(self.sim, "ADR 6"), "OK")
        self.assertEqual((ask(self.sim, "OUT?"), ask(self.sim, "PV?"), ask(self.sim, "FLT?")),
                         ("OFF", "2", "00"))                    # safe start, OVP reset
        self.assertEqual(ask(self.sim, "OUT 1"), "OK")
        self.settle()
        self.assertEqual(ask(self.sim, "MODE?"), "CC")

    def test_auto_restart_returns_the_output(self):
        sim, clock = make(auto_restart=True, addressed_at_start=True)
        ask(sim, "OUT 1")
        sim.signals["ac_power"].force(0)
        ask(sim, "OUT?")
        sim.signals["ac_power"].force(1)
        ask(sim, "ADR 6")
        self.assertEqual(ask(sim, "OUT?"), "ON")

    def test_rst(self):
        ask(self.sim, "PV 3")
        ask(self.sim, "OUT 1")
        self.assertEqual(ask(self.sim, "RST"), "OK")
        self.assertEqual((ask(self.sim, "PV?"), ask(self.sim, "OUT?"), ask(self.sim, "OVP?")),
                         ("0", "OFF", "10.0"))


class OverTcp(unittest.TestCase):
    def test_power_cycle_from_the_control_port(self):
        sim = build({"name": "tdk", "type": "tdk_genesys", "port": 0, "turnaround_ms": 0,
                     "options": {"addressed_at_start": True}})
        with SimThread([sim]):
            line = helpers.LineClient(sim.port, term=b"\r")
            with ControlClient("127.0.0.1", sim.control_port) as ctl:
                line.send(b"OUT?\r")
                self.assertEqual(line.readline(1.0), b"OFF")
                ctl.set("ac_power", 0)
                ctl.release("ac_power")
                line.send(b"OUT?\r")
                self.assertIsNone(line.readline(0.3))
                line.send(b"ADR 6\r")
                self.assertEqual(line.readline(1.0), b"OK")
                self.assertEqual(ctl.get("output")["value"], 0.0)
            line.close()


if __name__ == "__main__":
    unittest.main()
