"""Configuration files: everything checked, unknown keys are errors with a clear message."""

import os
import shutil
import tempfile
import unittest

import helpers  # noqa: F401  (registers the test types)

from mist2sim.core import ConfigError, build, check_config, load_config

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, "..", "examples")


def entry(**kw):
    e = {"name": "e", "type": "test_echo", "port": 5000}
    e.update(kw)
    return e


class ConfigTest(unittest.TestCase):
    def assertConfigError(self, data, *words):
        with self.assertRaises(ConfigError) as ctx:
            for e in check_config(data):
                build(e)
        for w in words:
            self.assertIn(w, str(ctx.exception))

    def test_examples_load(self):
        for name in ("valvebox.yaml", "thermocouple.yaml"):
            for e in load_config(os.path.join(EXAMPLES, name)):
                sim = build(e)
                self.assertEqual(sim.TYPE, "libcom1")

    def test_defaults(self):
        sim = build(entry())
        self.assertEqual(sim.control_port, 6000)
        self.assertEqual((sim.baud, sim.bits_per_char, sim.turnaround_ms), (9600, 10, 0.0))
        self.assertEqual((sim.in_term, sim.out_term), (b"\n", b"\n"))
        self.assertEqual(sim.options, {"greeting": "hi"})
        sim = build(entry(control_port=7001, in_terminator=";FF", out_terminator="\r\n",
                          baud=19200, bits_per_char=11, turnaround_ms=16))
        self.assertEqual((sim.control_port, sim.in_term, sim.baud), (7001, b";FF", 19200))

    def test_errors(self):
        self.assertConfigError({"name": "x"}, "list")
        self.assertConfigError([], "list")
        self.assertConfigError(["text"], "mapping")
        self.assertConfigError([entry(bauds=9600)], "unknown key", "bauds", "allowed")
        self.assertConfigError([{"name": "a", "type": "test_echo"}], "'port' is missing")
        self.assertConfigError([entry(type="warp_drive")], "unknown type", "warp_drive", "libcom1")
        self.assertConfigError([entry(port="5000")], "port number")
        self.assertConfigError([entry(port=70000)], "port number")
        self.assertConfigError([entry(), entry()], "used twice")
        self.assertConfigError([entry(), entry(name="f", port=6000)], "port 6000", "used by e")
        self.assertConfigError([entry(baud=0)], "baud")
        self.assertConfigError([entry(baud="fast")], "baud")
        self.assertConfigError([entry(in_terminator="")], "in_terminator")
        self.assertConfigError([entry(options={"greting": "x"})], "unknown option", "greting",
                               "allowed: greeting")
        self.assertConfigError([entry(options={"greeting": 3})], "greeting", "must be str")
        self.assertConfigError([entry(options=[1])], "mapping")

    def test_libcom1_errors(self):
        def lc(**options):
            o = {"channels": [{"id": "s1", "behaviour": "relay"}]}
            o.update(options)
            return [entry(type="libcom1", options=o)]

        self.assertConfigError([entry(type="libcom1")], "'channels' is required")
        self.assertConfigError(lc(channels=[{"id": "s10"}]), "one character and one digit")
        self.assertConfigError(lc(channels=[{"id": "s1", "behaviour": "magic"}]), "behaviour")
        self.assertConfigError(lc(channels=[{"id": "s1", "behaviour": "relay", "noise": 1}]),
                               "unknown key", "noise")
        self.assertConfigError(lc(channels=[{"id": "s1", "access": "x"}]), "access")
        self.assertConfigError(lc(channels=[{"id": "s1"}, {"id": "s1"}]), "s1")
        self.assertConfigError(lc(channels=[{"id": "s1", "value": "high"}]), "number")
        self.assertConfigError(lc(number_format="%f"), "number_format")
        self.assertConfigError(lc(out_buffer=10), "out_buffer")
        self.assertConfigError(lc(on_timeout={"z9": 0}), "on_timeout")
        self.assertConfigError(lc(identiy="x"), "unknown option", "identiy")

    def test_new_device_file_is_discovered(self):
        from mist2sim import devices
        from mist2sim.core import TYPES, registry
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "zz_new_device.py"), "w") as f:
            f.write("from mist2sim.core import Simulator, register\n"
                    "@register('zz_new')\nclass New(Simulator):\n    pass\n")
        with open(os.path.join(tmp, "zz_broken.py"), "w") as f:
            f.write("raise RuntimeError('half written')\n")
        devices.__path__.append(tmp)
        try:
            with self.assertLogs("mist2sim", "ERROR"):
                check_config([entry(type="zz_new")])
            self.assertIn("zz_new", TYPES)
            self.assertIn("half written", registry.IMPORT_ERRORS["zz_broken"])
        finally:
            devices.__path__.remove(tmp)
            registry.IMPORT_ERRORS.pop("zz_broken", None)
            shutil.rmtree(tmp)

    def test_yaml_file_errors(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("- name: [unclosed\n")
        self.addCleanup(os.unlink, f.name)
        with self.assertRaises(ConfigError) as ctx:
            load_config(f.name)
        self.assertIn("not valid YAML", str(ctx.exception))
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/x.yaml")


if __name__ == "__main__":
    unittest.main()
