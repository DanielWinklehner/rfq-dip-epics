"""The service logic without sockets: configuration, scaling, limits, "not known", the sim
backend, the communication timeout and its two actions."""

import math
import os
import unittest

from mist2daq import config as cfg
from mist2daq.backends import SimBackend, make_backend
from mist2daq.service import Daq

HERE = os.path.dirname(os.path.abspath(__file__))
DAQ = os.path.dirname(HERE)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def base(**service):
    return {
        "service": dict(service),
        "backend": {"type": "sim", "sim": {"inputs": {
            "Dev1/ai0": {"follow": "Dev1/ao0", "gain": 1.0, "tau_s": 2.0}}}},
        "channels": [
            {"id": "o1", "name": "set", "direction": "out", "physical": "Dev1/ao0", "unit": "A",
             "per_volt": 10.0, "offset": 0.0, "limits": [0.0, 80.0], "volts": [0.0, 10.0],
             "ramp_rate": 20.0},
            {"id": "i1", "name": "mon", "direction": "in", "physical": "Dev1/ai0", "unit": "A",
             "per_volt": 10.0, "offset": 0.0, "volts": [-10.0, 10.0]},
        ],
    }


def make(data=None, **service):
    clock = Clock()
    c = cfg.parse(data or base(**service))
    backend = SimBackend(c, clock)
    daq = Daq(c, backend, clock)
    return daq, backend, clock


class NotKnown(unittest.TestCase):
    def test_before_the_first_set(self):
        daq, backend, _ = make()
        self.assertEqual(daq.service(0, "A")[0], "onan:0")
        self.assertEqual(daq.service(1, "go1")[0], "onan")
        self.assertEqual(backend.writes, 0)                       # nothing written at the start
        self.assertEqual(backend.outputs_written(), {})
        self.assertIsNone(daq.status()["channels"]["o1"]["held"])

    def test_after_a_set(self):
        daq, backend, _ = make()
        self.assertEqual(daq.service(0, "So125")[0], "ok")
        self.assertEqual(daq.service(1, "go1")[0], "o25")
        self.assertEqual(backend.outputs_written(), {"Dev1/ao0": 2.5})

    def test_failed_write_makes_it_unknown_again(self):
        daq, backend, _ = make()
        daq.service(0, "So125")
        backend.fail_writes = True
        self.assertEqual(daq.service(1, "So130")[0], "ERR7")
        self.assertEqual(daq.service(2, "go1")[0], "onan")
        self.assertEqual(daq.counts["sets_failed_backend"], 1)


class Identity(unittest.TestCase):
    def test_long_identity_fits(self):
        data = base()
        data["service"]["identity"] = "DipoleMagnetSupplyDAQ-LabComputer-NI-USB-6001"
        daq, _, _ = make(data)
        self.assertEqual(daq.service(0, "I")[0],
                         "oID=DipoleMagnetSupplyDAQ-LabComputer-NI-USB-6001;FW=mist2daq-0.1;PROTO=2;CH=o1,i1")


class Scaling(unittest.TestCase):
    def test_offset_and_both_directions(self):
        data = base()
        data["channels"][0].update(per_volt=-4.0, offset=20.0, limits=[-20.0, 20.0], volts=[0.0, 10.0])
        data["channels"][1].update(per_volt=5.0, offset=-1.0)
        data["backend"]["sim"]["inputs"]["Dev1/ai0"]["tau_s"] = 0.0
        daq, backend, _ = make(data)
        self.assertEqual(daq.service(0, "So112")[0], "ok")        # (12 - 20) / -4 = 2 V
        self.assertAlmostEqual(backend.out["Dev1/ao0"], 2.0)
        self.assertEqual(daq.service(1, "gi1")[0], "o9")          # -1 + 5 * 2 V
        self.assertEqual(daq.service(2, "So1-20")[0], "ok")       # 10 V
        self.assertAlmostEqual(backend.out["Dev1/ao0"], 10.0)
        self.assertEqual(daq.service(3, "So120")[0], "ok")        # 0 V
        self.assertAlmostEqual(backend.out["Dev1/ao0"], 0.0)

    def test_to_volts(self):
        daq, _, _ = make()
        c = daq.config.outputs[0]
        self.assertEqual(Daq.to_volts(c, 25.0), 2.5)


class Limits(unittest.TestCase):
    def test_unit_limits(self):
        daq, backend, _ = make()
        self.assertEqual(daq.service(0, "So180")[0], "ok")        # the limit itself is allowed
        self.assertEqual(daq.service(1, "So180.01")[0], "ERR5")
        self.assertEqual(daq.service(2, "So1-0.001")[0], "ERR5")
        self.assertEqual(daq.service(3, "so190")[0], "ERR5")      # also unacknowledged
        self.assertEqual(daq.service(4, "go1")[0], "o80")          # held unchanged
        self.assertAlmostEqual(backend.out["Dev1/ao0"], 8.0)       # output unchanged
        self.assertEqual(backend.writes, 1)
        self.assertEqual(daq.counts["sets_refused_limit"], 3)

    def test_volt_limits(self):
        data = base()
        data["channels"][0].update(limits=[0.0, 200.0], volts=[0.0, 5.0])
        daq, backend, _ = make(data)
        self.assertEqual(daq.service(0, "So150")[0], "ok")        # 5 V
        self.assertEqual(daq.service(1, "So150.1")[0], "ERR5")    # 5.01 V
        self.assertEqual(backend.writes, 1)

    def test_limit_with_decimals_as_float(self):
        data = base()
        data["channels"][0].update(limits=[0.0, 12.3], volts=[0.0, 10.0])
        daq, _, _ = make(data)
        self.assertEqual(daq.service(0, "So112.3")[0], "ok")
        self.assertEqual(daq.service(1, "So112.300001")[0], "ERR5")


class SimBackendLag(unittest.TestCase):
    def test_first_order_lag(self):
        daq, backend, clock = make()
        daq.service(0, "So150")                                     # 5 V, tau 2 s
        self.assertEqual(daq.service(1, "gi1")[0], "o0")
        clock.t += 2.0
        v = float(daq.service(2, "gi1")[0][1:])
        self.assertAlmostEqual(v, 50.0 * (1 - math.exp(-1)), places=3)
        clock.t += 20.0
        self.assertAlmostEqual(float(daq.service(3, "gi1")[0][1:]), 50.0, places=2)

    def test_fixed_input_and_initial_volts(self):
        data = base()
        data["backend"]["sim"] = {"initial_volts": {"Dev1/ao0": 1.0}, "inputs": {"Dev1/ai0": {"volts": 0.5}}}
        daq, backend, _ = make(data)
        self.assertEqual(daq.service(0, "A")[0], "onan:5")          # held still not known
        self.assertEqual(backend.out["Dev1/ao0"], 1.0)

    def test_read_failure_sends_nan(self):
        daq, backend, _ = make()

        def broken():
            from mist2daq.backends import BackendError
            raise BackendError("unplugged")
        backend.read_inputs = broken
        self.assertEqual(daq.service(0, "A")[0], "onan:nan")


class CommLost(unittest.TestCase):
    def test_hold_is_the_default(self):
        daq, backend, clock = make()
        daq.service(0, "So150")
        daq.service(6000)                                           # 5 s timeout passed
        self.assertTrue(daq.device.comm_lost)
        self.assertEqual(daq.ramping, {})
        clock.t += 60
        daq.step_ramps()
        self.assertEqual(backend.writes, 1)
        self.assertEqual(daq.held["o1"], 50.0)

    def test_ramp_to_zero(self):
        daq, backend, clock = make(on_comm_lost="ramp_to_zero")
        daq.service(0, "So150")
        daq.service(5000)
        self.assertIn("o1", daq.ramping)
        clock.t += 1.0
        daq.step_ramps()
        self.assertAlmostEqual(daq.held["o1"], 30.0, places=4)      # 20 A/s
        clock.t += 1.0
        daq.step_ramps()
        clock.t += 1.0
        daq.step_ramps()
        self.assertEqual(daq.held["o1"], 0.0)
        self.assertEqual(daq.ramping, {})
        self.assertAlmostEqual(backend.out["Dev1/ao0"], 0.0)

    def test_ramp_ends_on_a_set_and_skips_unknown(self):
        daq, backend, clock = make(on_comm_lost="ramp_to_zero")
        daq.service(0, "A")
        daq.service(5000)                                           # nothing set: nothing to ramp
        self.assertTrue(daq.device.comm_lost)
        self.assertEqual(daq.ramping, {})
        daq.service(5001, "So150")
        daq.service(10001)
        clock.t += 1.0
        daq.step_ramps()
        daq.service(10002, "So140")
        self.assertEqual(daq.ramping, {})
        self.assertEqual(daq.held["o1"], 40.0)


class Config(unittest.TestCase):
    def bad(self, mutate, text):
        data = base()
        mutate(data)
        with self.assertRaises(cfg.ConfigError) as ctx:
            cfg.parse(data)
        self.assertIn(text, str(ctx.exception))

    def test_errors(self):
        self.bad(lambda d: d["channels"][0].update(per_volt=0), "per_volt must not be 0")
        self.bad(lambda d: d["channels"][0].update(id="o"), "id must be")
        self.bad(lambda d: d["channels"][0].pop("limits"), "limits is missing")
        self.bad(lambda d: d["channels"][0].update(colour="red"), "unknown key")
        self.bad(lambda d: d["channels"][1].update(limits=[0, 1]), "unknown key")
        self.bad(lambda d: d["channels"][0].update(limits=[5, 1]), "low < high")
        self.bad(lambda d: d["channels"][0].update(limits=[200, 300]), "no value in common")
        self.bad(lambda d: d["channels"][1].update(id="o1"), "not unique")
        self.bad(lambda d: d["service"].update(on_comm_lost="zero"), "hold or ramp_to_zero")
        self.bad(lambda d: d["service"].update(listen_prot=1), "unknown key")
        self.bad(lambda d: d["service"].update(identity="a;b"), "identity")

        def ramp_without_rate(d):
            d["service"]["on_comm_lost"] = "ramp_to_zero"
            d["channels"][0].pop("ramp_rate")
        self.bad(ramp_without_rate, "ramp_rate")

        def zero_outside(d):
            d["service"]["on_comm_lost"] = "ramp_to_zero"
            d["channels"][0]["limits"] = [5.0, 80.0]
        self.bad(zero_outside, "outside limits")

    def test_shipped_files_load(self):
        for name in ("config/dipole.yaml",):
            c = cfg.load(os.path.join(DAQ, name))
            self.assertEqual(c.service["on_comm_lost"], "hold")
            self.assertEqual(c.backend["type"], "nidaqmx")
        case = os.path.join(DAQ, "..", "emulation", "devtest", "dipole", "daq.yaml")
        c = cfg.load(case)
        make_backend(c)                                            # sim: checks its own keys


if __name__ == "__main__":
    unittest.main()
