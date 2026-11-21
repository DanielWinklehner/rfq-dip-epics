"""nt20_monitor: pump model, relays, the talk-only record output and the coupling to the Opta."""

import unittest

from helpers import LineClient, wait_until

from mist2sim.control import ControlClient
from mist2sim.core import FakeClock, SimThread, build
from mist2sim.devices.nt20_monitor import format_record

FAST = {"ramp_up_s": 10.0, "run_down_s": 20.0, "brake_s": 5.0, "rated_speed_hz": 1000.0,
        "current_noise_a": 0.0}


def nt20(clock=None, **options):
    return build({"name": "nt20", "type": "nt20_monitor", "port": 0, "control_port": 0,
                  "options": dict(FAST, **options)}, clock=clock)


def contacts(sim):
    return [sim.signals[n].value for n in ("normal", "accel", "failure")]


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.sim = nt20(self.clock)

    def advance(self, seconds, step=0.1):
        for _ in range(int(round(seconds / step))):
            self.clock.advance(step)
            self.sim.step_couplings()

    def test_start_accelerate_normal_stop(self):
        sim = self.sim
        self.advance(1)
        self.assertEqual(contacts(sim), [0, 0, 0])
        sim.run.target = 1
        self.advance(1)
        self.assertEqual(contacts(sim), [0, 1, 0])
        self.assertAlmostEqual(sim.speed.value, 100.0, delta=1)
        self.assertEqual(sim.current.value, 2.5)
        self.advance(7.5)                                 # 850 Hz, above 80 %
        self.assertEqual(contacts(sim), [1, 0, 0])
        self.advance(5)
        self.assertEqual(sim.speed.value, 1000.0)
        self.assertEqual(sim.current.value, 0.6)
        sim.run.target = 0
        self.advance(2)                                   # runs down: 900 Hz, still NORMAL
        self.assertEqual(contacts(sim), [1, 0, 0])
        self.assertEqual(sim.current.value, 0.0)
        self.advance(20)
        self.assertEqual((contacts(sim), sim.speed.value), ([0, 0, 0], 0.0))

    def test_trip_latches_until_stop(self):
        sim = self.sim
        sim.run.target = 1
        self.advance(12)
        sim.add_fault("trip")
        self.assertEqual(contacts(sim), [0, 0, 1])
        self.advance(2)                                   # brakes: 200 Hz/s
        self.assertAlmostEqual(sim.speed.value, 600.0, delta=1)
        self.assertEqual(sim.state(), "ERR")
        self.advance(10)
        self.assertEqual(contacts(sim), [0, 0, 1])        # still failed while run is on
        sim.run.target = 0
        self.advance(0.1)
        self.assertEqual(contacts(sim), [0, 0, 0])
        self.assertEqual(sim.fault_list(), [])            # the stop also ended the fault

    def test_records(self):
        self.assertEqual(format_record(833.4, 1.254, "ACC"), "NT20 f=0833Hz I=1.25A ACC")
        sim = self.sim
        self.assertEqual(sim.tick(0.0), 0.1)
        self.assertEqual(sim.outbox, [b"NT20 f=0000Hz I=0.00A STP"])
        self.assertEqual(sim.tick(5.0), 5.1)              # next record due at 8 s
        self.assertEqual(len(sim.outbox), 1)
        sim.tick(8.0)
        self.assertEqual(len(sim.outbox), 2)
        self.assertEqual(sim.process(b"anything"), [])    # it never answers


class TcpTest(unittest.TestCase):
    def test_records_on_the_line_and_silent(self):
        sim = nt20(period_s=0.2)
        with SimThread([sim]):
            c = LineClient(sim.port, term=b"\r\n")
            self.addCleanup(c.close)
            self.assertTrue(c.readline(1.0).startswith(b"NT20 f="))
            self.assertIsNotNone(c.readline(1.0))
            with ControlClient("127.0.0.1", sim.control_port) as ctl:
                ctl.fault("silent")
                c.readline(0.3)                           # one may be on its way
                self.assertIsNone(c.readline(0.5))
                ctl.clear()
                self.assertIsNotNone(c.readline(1.0))

    def test_coupled_to_an_opta(self):
        opta = build({"name": "opta", "type": "libcom1", "port": 0, "control_port": 0,
                      "out_terminator": "\n", "options": {
                          "identity": "TurboOpta", "number_format": "g", "channels": [
                              {"id": "r1", "behaviour": "relay"},
                              {"id": "n1"}, {"id": "a1"}, {"id": "f1"}]}})
        with SimThread([opta]):
            pump = nt20(opta_port=opta.control_port, couple_s=0.05)
            with SimThread([pump]):
                c = LineClient(opta.port)
                self.addCleanup(c.close)
                self.assertTrue(wait_until(lambda: pump.coupled, 2.0))
                self.assertEqual(c.ask(b"Sr11"), b"ok")
                self.assertTrue(wait_until(lambda: c.ask(b"A") == b"o1:0:1:0", 2.0))
                with ControlClient("127.0.0.1", pump.control_port) as ctl:
                    ctl.fault("trip")
                self.assertTrue(wait_until(lambda: c.ask(b"A") == b"o1:0:0:1", 2.0))
                self.assertEqual(c.ask(b"Sr10"), b"ok")
                self.assertTrue(wait_until(lambda: c.ask(b"A") == b"o0:0:0:0", 2.0))


if __name__ == "__main__":
    unittest.main()
