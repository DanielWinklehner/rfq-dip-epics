"""libcom1 engine details not covered by the replay, and the configurable simulator."""

import os
import re
import sys
import time
import unittest

from helpers import LineClient

from mist2sim.control import ControlClient
from mist2sim.core import ConfigError, FakeClock, SimThread, build, load_config
from mist2sim.devices.libcom1 import Channel, Engine, format_value, from_line_buffer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import libcom1_replay  # noqa: E402

EXAMPLES = os.path.join(HERE, "..", "examples")


def engine(fmt="g", n=8, **kw):
    store = {}
    chans = [Channel("s", i, (lambda i=i: store.get(i, 0.0)),
                     (lambda v, i=i: store.__setitem__(i, v))) for i in range(1, n + 1)]
    return Engine(chans, number_format=fmt, **kw), store


class EngineTest(unittest.TestCase):
    def ask(self, eng, line, now=0):
        return eng.service(now, line).reply

    def test_avr_format(self):
        self.assertEqual(format_value(25.0, "avr"), "+2.5e+01")
        self.assertEqual(format_value(20.0, "avr"), "+2.e+01")
        self.assertEqual(format_value(-0.0, "avr"), "-0.e+00")
        self.assertEqual(format_value(float("nan"), "avr"), "nan")
        self.assertEqual(format_value(float("-inf"), "g"), "-inf")

    def test_float32(self):
        eng, store = engine()
        self.assertEqual(self.ask(eng, "Ss13e38"), "ok")
        self.assertEqual(self.ask(eng, "Ss13.5e38"), "ERR5")      # finite as double, inf as float
        self.assertEqual(self.ask(eng, "Ss116777217"), "ok")
        self.assertEqual(store[1], 16777216.0)

    def test_hex_only_where_strtod_has_it(self):
        self.assertEqual(self.ask(engine("g")[0], "Ss10x10"), "ok")
        self.assertEqual(self.ask(engine("avr")[0], "Ss10x10"), "ERR5")
        self.assertEqual(self.ask(engine("g")[0], "Ss1 5\t"), "ok")

    def test_line_buffer(self):
        self.assertEqual(from_line_buffer("A\r"), "A")
        self.assertIsNone(from_line_buffer("\r"))
        self.assertEqual(from_line_buffer("x" * 127, 128), "x" * 127)
        self.assertEqual(from_line_buffer("x" * 128, 128), "!")
        eng, _ = engine()
        self.assertEqual(self.ask(eng, from_line_buffer("s" * 200)), "ERR0")
        self.assertEqual(self.ask(eng, "A\0junk"), "o0:0:0:0:0:0:0:0")

    def test_output_buffer_limits(self):
        eng, _ = engine(out_buffer=114)                 # min_out_buffer_size(8)
        self.assertEqual(self.ask(eng, "P100"), "ERR2")  # streaming needs 17 more
        eng.name = "x" * 100
        self.assertEqual(self.ask(eng, "I"), "ERR2")
        with self.assertRaises(ValueError):
            engine(out_buffer=113)

    def test_comm_timeout_and_due_time(self):
        eng, _ = engine()
        fired = []
        eng.set_comm_timeout(500, lambda: fired.append(1))
        eng.service(0)
        self.assertEqual(eng.ms_until_due(), 500)
        eng.service(200, "?")                      # garbage is no sign of life
        self.assertEqual(eng.ms_until_due(), 300)
        eng.service(499)
        self.assertEqual(fired, [])
        eng.service(500)
        self.assertEqual((fired, eng.comm_lost, eng.ms_until_due()), ([1], True, None))
        eng.service(600, "A")
        self.assertFalse(eng.comm_lost)

    def test_stream_wraps_and_skips(self):
        eng, _ = engine(n=1, out_buffer=160)
        eng.service(0, "P10")
        self.assertEqual(eng.service(10).frames, ["t0:10:0"])
        self.assertEqual(eng.service(55).frames, ["t1:55:0"])   # late: skips ahead, no burst
        self.assertEqual(eng.service(60).frames, [])
        self.assertEqual(eng.service(65).frames, ["t2:65:0"])
        eng.seq = 65535
        self.assertEqual(eng.service(75).frames, ["t65535:75:0"])
        self.assertEqual(eng.service(85).frames, ["t0:85:0"])

    def test_protocol_1(self):
        """A board flashed before protocol 2. Expected replies: the library of commit 9cb8f18^
        (protocol 1, %g branch), built on the host with five channels f1..f5 holding these
        values and given these lines through communicate(), on 2026-11-24 (task T26)."""
        values = [1.0, 0.095238, 0.0, 1.904762, 2.5e-7]
        chans = [Channel("f", i + 1, (lambda i=i: values[i]), (lambda v: None)) for i in range(5)]
        eng = Engine(chans, number_format="g", out_buffer=128, protocol=1)
        expected = [("A", "o1:0.095238:0:1.90476:2.5e-07"), ("I", "ERR0"), ("gf1", "ERR0"),
                    ("Sf11", "ERR0"), ("P100", "ERR0"), ("sf12.5", None), ("q01f13", "of1+10000+"),
                    ("q01f93", "ERR4"), ("x", "ERR0"), ("A", "o1:0.095238:0:1.90476:2.5e-07")]
        self.assertEqual([(line, self.ask(eng, line)) for line, _ in expected], expected)
        self.assertEqual(self.ask(engine(protocol=2)[0], "I")[:3], "oID")
        with self.assertRaises(ValueError):
            engine(protocol=3)

    def test_replay_parser_reads_the_whole_table(self):
        with open(libcom1_replay.DEFAULT_SCRIPT) as f:
            text = f.read()
        libcom1_replay.check_device(text)
        steps = libcom1_replay.parse_steps(text)
        self.assertEqual(steps[0], (0, "I"))
        self.assertEqual(steps[-1], (3600, None))
        self.assertEqual(len(steps), len(re.findall(r'\{\s*\d+\s*,\s*(?:"|nullptr)', text)))


class SimulatorTest(unittest.TestCase):
    def load(self, name, **kw):
        (e,) = load_config(os.path.join(EXAMPLES, name))
        e.update(port=0, control_port=0)
        return build(e, **kw)

    def test_valvebox_relay_semantics(self):
        sim = self.load("valvebox.yaml")
        self.assertEqual(sim.process(b"Ss11"), [b"ok"])
        self.assertEqual(sim.process(b"gs1\r"), [b"o+1.e+00"])
        self.assertEqual(sim.process(b"Ss22"), [b"ok"])         # only exactly 1 energises
        self.assertEqual(sim.process(b"gs2"), [b"o+0.e+00"])
        self.assertEqual(sim.process(b""), [])
        sim.signals["s3"].force(1)
        self.assertEqual(sim.process(b"A"), [b"o+1.e+00:+0.e+00:+1.e+00:+0.e+00:+0.e+00:"
                                             b"+0.e+00:+0.e+00:+0.e+00"])

    def test_thermocouple(self):
        sim = self.load("thermocouple.yaml")
        info = sim.process(b"I")[0].decode()
        self.assertTrue(info.endswith("CH=t1,t2,t3,t4,j1,j2,j3,j4,f1,f2,f3,f4,a1,a2,a3,a4"))
        values = sim.process(b"A")[0][1:].split(b":")
        self.assertEqual(len(values), 16)
        self.assertAlmostEqual(float(values[0]), 22.0, delta=0.5)
        self.assertEqual(sim.process(b"St1100"), [b"ok"])        # dummy_set: accepted, ignored
        self.assertAlmostEqual(float(sim.process(b"gt1")[0][1:]), 22.0, delta=0.5)
        self.assertEqual(sim.settings["baud"], 19200)

    def test_on_timeout_with_fake_clock(self):
        clock = FakeClock()
        sim = build({"name": "ilk", "type": "libcom1", "port": 0, "options": {
            "number_format": "g", "comm_timeout_ms": 1000, "on_timeout": {"r1": 0},
            "channels": [{"id": "r1", "behaviour": "readback"}]}}, clock=clock)
        self.assertEqual(sim.process(b"Sr15"), [b"ok"])
        self.assertAlmostEqual(sim.tick(sim.now()), 1.0005)
        clock.advance(1.0)
        sim.tick(sim.now())
        self.assertEqual(sim.process(b"gr1"), [b"o0"])

    def test_protocol_1_option(self):
        def p1(**options):
            return build({"name": "flow", "type": "libcom1", "port": 0, "options": dict(
                {"number_format": "g", "protocol": 1,
                 "channels": [{"id": "f1", "value": 1.5}, {"id": "f2"}]}, **options)})
        sim = p1()
        self.assertEqual(sim.process(b"A"), [b"o1.5:0"])
        with self.assertLogs(sim.log, "INFO") as logged:
            self.assertEqual(sim.process(b"I"), [b"ERR0"])
            self.assertEqual(sim.process(b"Sf11"), [b"ERR0"])
        self.assertEqual(logged.output, ["INFO:%s:protocol 1: 'I' answered ERR0" % sim.log.name,
                                         "INFO:%s:protocol 1: 'Sf11' answered ERR0" % sim.log.name])
        self.assertEqual(sim.process(b"sf12"), [])
        for bad in ({"protocol": 3}, {"protocol": True}, {"comm_timeout_ms": 1000}):
            with self.assertRaises(ConfigError):
                p1(**bad)

    def test_trip_is_not_supported(self):
        with self.assertRaises(Exception):
            self.load("valvebox.yaml").add_fault("trip")

    def test_streaming_over_tcp(self):
        sim = self.load("valvebox.yaml")
        with SimThread([sim]):
            c = LineClient(sim.port, term=b"\r\n")
            self.addCleanup(c.close)
            self.assertEqual(c.ask(b"P50"), b"ok")
            t0 = time.monotonic()
            frames = [c.readline(1.0) for _ in range(4)]
            dt = time.monotonic() - t0
            self.assertEqual([f.split(b":")[0] for f in frames], [b"t0", b"t1", b"t2", b"t3"])
            ms = [int(f.split(b":")[1]) for f in frames]
            for a, b in zip(ms, ms[1:]):                # loop() jitter of a millisecond
                self.assertAlmostEqual(b - a, 50, delta=2)
            self.assertAlmostEqual(ms[3] - ms[0], 150, delta=2)
            self.assertAlmostEqual(dt, 0.2, delta=0.03)
            c.send(b"P0\n")
            while c.readline(0.5) != b"ok":
                pass
            self.assertIsNone(c.readline(0.2))
            with ControlClient("127.0.0.1", sim.control_port) as ctl:
                ctl.set("s5", 1)
                self.assertEqual(c.ask(b"gs5"), b"o+1.e+00")
                self.assertIn("trip", ctl.call({"cmd": "fault", "mode": "trip"})["error"])


if __name__ == "__main__":
    unittest.main()
