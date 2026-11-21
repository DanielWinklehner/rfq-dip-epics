"""mks_rs485: framing, ACK/NAK, addressing on the bus, flow following the set point."""

import unittest

from helpers import LineClient

from mist2sim.control import ControlClient
from mist2sim.core import FakeClock, SimThread, build


def bus(units=({"address": 254},), clock=None, **options):
    options["units"] = list(units)
    return build({"name": "mfc", "type": "mks_rs485", "port": 0, "control_port": 0,
                  "options": options}, clock=clock or FakeClock())


class FramingTest(unittest.TestCase):
    def test_queries_and_sets_of_the_supplement(self):
        sim = bus()
        self.assertEqual(sim.process(b"@@@254S?"), [b"@@@000ACK-20.00"])
        self.assertEqual(sim.process(b"@@@254S!50"), [b"@@@000ACK50"])
        self.assertEqual(sim.process(b"@254S?"), [b"@@@000ACK50.00"])     # one '@' is enough
        self.assertEqual(sim.process(b"@@@254WK?"), [b"@@@000ACKOFF"])
        self.assertEqual(sim.process(b"@@@254WK!ON"), [b"@@@000ACKON"])
        self.assertEqual(sim.process(b"@@@254WK?"), [b"@@@000ACKON"])
        self.assertEqual(sim.process(b"@@@254FS?"), [b"@@@000ACK100"])
        self.assertEqual(sim.process(b"@@@254U?"), [b"@@@000ACKSCCM"])
        self.assertEqual(sim.process(b"@@@254T?"), [b"@@@000ACKO"])
        self.assertEqual(sim.process(b"@@@254VO?"), [b"@@@000ACKNORMAL"])

    def test_naks(self):
        sim = bus()
        self.assertEqual(sim.process(b"@@@254s?"), [b"@@@000NAK17"])      # lower case
        self.assertEqual(sim.process(b"@@@254XYZ?"), [b"@@@000NAK17"])
        self.assertEqual(sim.process(b"@@@254S"), [b"@@@000NAK10"])       # neither ! nor ?
        self.assertEqual(sim.process(b"@@@254S!abc"), [b"@@@000NAK12"])
        self.assertEqual(sim.process(b"@@@254S!150"), [b"@@@000NAK12"])   # above 140 %
        self.assertEqual(sim.process(b"@@@254PG?"), [b"@@@000NAK13"])     # only in Cal mode
        self.assertEqual(sim.process(b"@@@254OM!CAL_MODE"), [b"@@@000ACKCAL_MODE"])
        self.assertEqual(sim.process(b"@@@254PG?"), [b"@@@000ACKN2"])
        self.assertEqual(sim.process(b"254S?"), [])                       # no '@': not a message

    def test_trip_answers_nak98(self):
        sim = bus()
        sim.add_fault("trip")
        self.assertEqual(sim.process(b"@@@254S!10"), [b"@@@000NAK98"])
        sim.clear_faults()
        self.assertEqual(sim.process(b"@@@254S!10"), [b"@@@000ACK10"])

    def test_echo_can_be_switched_off(self):
        self.assertEqual(bus(set_reply_echo=False).process(b"@@@254S!10"), [b"@@@000ACK"])


class BusTest(unittest.TestCase):
    def test_addresses(self):
        sim = bus([{"address": 1, "full_scale": 200.0}, {"address": 2}])
        self.assertEqual(sim.process(b"@@@001S!25"), [b"@@@000ACK25"])
        self.assertEqual(sim.process(b"@@@002S?"), [b"@@@000ACK-20.00"])
        self.assertEqual(sim.process(b"@@@001SX?"), [b"@@@000ACK50.00"])
        self.assertEqual(sim.process(b"@@@003S?"), [])                    # nobody there
        self.assertEqual(sim.process(b"@@@254CA?"), [b"@@@000ACK001", b"@@@000ACK002"])
        self.assertEqual(sim.process(b"@@@255S!5"), [])                   # all execute, none answers
        self.assertEqual(sim.signals["1.setpoint"].value, 5.0)
        self.assertEqual(sim.signals["2.setpoint"].value, 5.0)
        sim.add_fault("silent", unit=2)
        self.assertEqual(sim.process(b"@@@002S?"), [])
        self.assertEqual(sim.process(b"@@@001S?"), [b"@@@000ACK5.00"])

    def test_flow_follows_set_point(self):
        clock = FakeClock()
        sim = bus([{"address": 254, "full_scale": 50.0, "tau_s": 2.0, "noise": 0.0}], clock=clock)
        self.assertEqual(sim.process(b"@@@254F?"), [b"@@@000ACK0.00"])     # -20 %: valve closed
        sim.process(b"@@@254S!80")
        clock.advance(2.0)
        self.assertAlmostEqual(float(sim.process(b"@@@254F?")[0][9:]), 80 * 0.632, delta=0.1)
        clock.advance(20.0)
        self.assertEqual(sim.process(b"@@@254F?"), [b"@@@000ACK80.00"])
        self.assertEqual(sim.process(b"@@@254FX?"), [b"@@@000ACK40.00"])
        sim.process(b"@@@254VO!FLOW_OFF")
        clock.advance(30.0)
        self.assertEqual(sim.process(b"@@@254F?"), [b"@@@000ACK0.00"])

    def test_over_tcp_with_semicolon_ff_framing(self):
        sim = bus([{"address": 254}], clock=None)
        with SimThread([sim]):
            c = LineClient(sim.port, term=b";FF")
            self.addCleanup(c.close)
            c.send(b"@@@254S!12.5;FF@@@254S?;FF")
            self.assertEqual(c.readline(1.0), b"@@@000ACK12.5")
            self.assertEqual(c.readline(1.0), b"@@@000ACK12.50")
            with ControlClient("127.0.0.1", sim.control_port) as ctl:
                self.assertEqual(ctl.get("254.setpoint")["value"], 12.5)
                ctl.set("254.flow", 33.0)                                  # a plant model
            c.send(b"@@@254F?;FF")
            self.assertAlmostEqual(float(c.readline(1.0)[9:]), 33.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
