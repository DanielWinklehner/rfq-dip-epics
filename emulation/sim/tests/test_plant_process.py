"""The plant process with the real simulators of the emulation, in-process on free ports.

The simulators come from config/rack.yaml and config/hv.yaml (ports replaced by free ones, the
turbopumps made fast). The actuators are moved through the device protocols (sim.process, the
same parser the IOC's bytes go through), the results are read on the control ports.
"""

import copy
import logging
import os
import time
import unittest

from helpers import wait_until

from mist2sim.control import ControlClient
from mist2sim.core import SimThread, build, load_config
from mist2sim.plant import Plant, PlantThread, load_plant_config
from mist2sim.plant.process import split_signal

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "..", "config")
PUMPS = ("nt20_1", "nt20_2")
RESTARTED = "aim"           # this one runs in its own thread, to be stopped and started again


def entries():
    out = {}
    for name in ("rack.yaml", "hv.yaml"):
        for e in load_config(os.path.join(CONFIG, name)):
            e = copy.deepcopy(e)
            e["port"], e["control_port"] = 0, 0
            out[e["name"]] = e
    for p in PUMPS:
        out[p]["options"].update(ramp_up_s=1.0, run_down_s=2.0, couple_s=0.05)
    return out


def values(port, *names):
    with ControlClient("127.0.0.1", port) as c:
        sig = c.get()["signals"]
    return [sig[n]["value"] for n in names] if names else sig


class PlantProcessTest(unittest.TestCase):
    def setUp(self):
        logging.getLogger("mist2sim").setLevel(logging.CRITICAL)
        self.entries = entries()
        self.sims = {n: build(e) for n, e in self.entries.items()}
        main = [s for n, s in self.sims.items() if n not in PUMPS + (RESTARTED,)]
        self.t_main = SimThread(main).__enter__()
        for p in PUMPS:
            self.sims[p].options["opta_port"] = self.sims["turbo_opta"].control_port
        self.t_pumps = SimThread([self.sims[p] for p in PUMPS]).__enter__()
        self.t_restart = SimThread([self.sims[RESTARTED]]).__enter__()
        cfg = load_plant_config(os.path.join(CONFIG, "plant.yaml"))
        for name, link in cfg["links"].items():
            link.update(host="127.0.0.1", port=self.sims[name].control_port)
        cfg["control"] = {"host": "127.0.0.1", "port": 0}
        cfg["retry_s"] = 0.2
        cfg["model"]["tc_tau_s"]["value"] = 1.0       # see a temperature move within a second
        self.cfg = cfg
        self.plant = Plant(cfg)
        self.t_plant = PlantThread(self.plant).__enter__()

    def tearDown(self):
        self.t_plant.stop()
        for t in (self.t_restart, self.t_pumps, self.t_main):
            t.__exit__(None, None, None)

    def device(self, name, *lines):
        sim = self.sims[name]
        thread = self.t_pumps if name in PUMPS else self.t_restart if name == RESTARTED else self.t_main
        return [thread.call(sim.process, line.encode()) for line in lines]

    def ctl(self, name):
        return self.sims[name].control_port

    def plant_get(self, name):
        with ControlClient("127.0.0.1", self.plant.control_port) as c:
            return c.get(name)["value"]

    def test_machine_reacts_and_lets_go(self):
        # every simulator connected, the process values under outside control
        self.assertTrue(wait_until(lambda: all(lk.up for lk in self.plant.links.values()), 5))
        self.assertTrue(wait_until(lambda: values(self.ctl("aim"))["pressure"]["external"], 3))
        base_t2 = values(self.ctl("thermocouple"), "t2")[0]
        # the pumps are not running: the pressure rises from the base pressure
        self.assertTrue(wait_until(lambda: values(self.ctl("aim"), "pressure")[0] > 2e-5, 6))

        # pumps: run relays on the turbopump Opta, fast run-up
        self.device("turbo_opta", "Sr11", "Sr21")
        self.assertTrue(wait_until(lambda: values(self.ctl("nt20_1"), "speed")[0] >= 1199, 5))
        self.assertTrue(wait_until(lambda: values(self.ctl("aim"), "pressure")[0] < 2.2e-6, 5))
        pumped = values(self.ctl("aim"), "pressure")[0]
        self.assertAlmostEqual(pumped, 2.0e-6, delta=2e-7)

        # gas: MFC 10 % of 50 sccm, shutoff valve still closed: no change
        self.device("mfc", "@@@254S!10")
        time.sleep(1.5)
        self.assertAlmostEqual(values(self.ctl("aim"), "pressure")[0], pumped, delta=2e-7)
        # foreline valve and shutoff valve open: the pressures rise
        self.device("valvebox", "Ss11", "Ss21")
        self.assertTrue(wait_until(lambda: values(self.ctl("aim"), "pressure")[0] > 50 * pumped, 4))
        p_diag, p_fl = values(self.ctl("gauges"), "p2", "p1")
        self.assertGreater(p_diag, 2 * 8e-7)
        self.assertGreater(p_fl, 3e-2)

        # filament 200 A, discharge 100 V / 24 A
        self.device("tdk", "ADR 6", "PV 8", "PC 200", "OUT 1")
        self.device("rek", "#1 REN", "#1 VCN 66.67", "#1 ICN 100", "#1 SW1")
        self.assertTrue(wait_until(lambda: values(self.ctl("rek"), "1.iout")[0] > 3.0, 8))
        tdk_load = values(self.ctl("tdk"), "load_ohm")[0]
        self.assertGreater(tdk_load, 0.02)                # hot filament
        self.assertTrue(wait_until(lambda: values(self.ctl("rek"), "1.iout")[0] > 6.0, 5))
        # the REK's own current limit still works: 5 A
        self.device("rek", "#1 ICN 20.83")
        self.assertTrue(wait_until(
            lambda: abs(values(self.ctl("rek"), "1.iout")[0] - 5.0) < 0.05, 3))
        self.assertLess(values(self.ctl("rek"), "1.vout")[0], 99.0)
        self.device("rek", "#1 ICN 100")

        # extraction: source 15 kV, puller 3 kV, cup out: nothing on the cup; cup in: beam
        self.device("mat_opt", "#1 REN", "#1 VCN 75", "#1 ICN 100", "#1 SW1",
                    "#2 REN", "#2 VCN 15", "#2 ICN 100", "#2 SW1")
        self.assertTrue(wait_until(lambda: self.plant_get("beam_current") > 1e-4, 3))
        self.assertEqual(values(self.ctl("faradaycup"), "c1")[0], 0.0)
        self.device("valvebox", "Ss41")
        self.assertTrue(wait_until(lambda: values(self.ctl("faradaycup"), "c1")[0] > 1e-4, 3))
        # the source supply delivers beam plus leakage
        self.assertTrue(wait_until(lambda: abs(values(self.ctl("mat_opt"), "1.iout")[0]
                                               / self.plant_get("source_current") - 1) < 0.02, 3))
        self.assertGreater(values(self.ctl("mat_opt"), "1.iout")[0], self.plant_get("beam_current"))

        # a temperature responds
        self.assertTrue(wait_until(lambda: values(self.ctl("thermocouple"), "t2")[0] > base_t2 + 3, 4))

        # a disturbance through the plant's control port: emission drops, discharge follows
        i_before = values(self.ctl("rek"), "1.iout")[0]
        with ControlClient("127.0.0.1", self.plant.control_port) as c:
            c.set("emission_factor", 0.5)
            self.assertIn("filament_temperature", c.info()["signals"])
        self.assertTrue(wait_until(lambda: values(self.ctl("rek"), "1.iout")[0] < 0.8 * i_before, 3))
        with ControlClient("127.0.0.1", self.plant.control_port) as c:
            c.release("emission_factor")
            c.set("pressure_burst_sccm", 20.0)
            self.assertTrue(wait_until(lambda: c.get("pressure_burst_sccm")["value"] < 20.0, 2))

        # stop and restart one simulator while the plant runs
        self.t_restart.__exit__(None, None, None)
        self.assertTrue(wait_until(lambda: not self.plant.links[RESTARTED].up, 3))
        steps = self.plant.steps
        time.sleep(0.5)
        self.assertGreater(self.plant.steps, steps + 2)          # the model keeps running
        self.assertTrue(values(self.ctl("rek"))["1.load_ohm"]["external"])
        fresh = build(dict(self.entries[RESTARTED], port=self.sims[RESTARTED].port,
                           control_port=self.sims[RESTARTED].control_port))
        self.sims[RESTARTED] = fresh
        self.t_restart = SimThread([fresh]).__enter__()
        self.assertTrue(wait_until(lambda: self.plant.links[RESTARTED].up, 3))
        self.assertTrue(wait_until(lambda: values(self.ctl("aim"))["pressure"]["external"], 2))
        self.assertGreater(values(self.ctl("aim"), "pressure")[0], 50 * pumped)

        # stop the plant: every signal back to the device's own behaviour
        self.t_plant.stop()
        for target in self.cfg["outputs"]:
            sim, sig = split_signal(target)
            self.assertFalse(values(self.ctl(sim))[sig]["external"], target)
        self.assertEqual(values(self.ctl("tdk"), "load_ohm")[0], 0.025)
        self.assertEqual(values(self.ctl("rek"), "1.load_ohm")[0], 5.0)
        self.assertEqual(values(self.ctl("faradaycup"), "c1")[0], 1.0e-6)
        self.assertEqual(values(self.ctl("thermocouple"), "t2")[0], 41.0)
        self.assertLess(values(self.ctl("aim"), "pressure")[0], 1e-5)

    def test_waits_for_simulators_that_are_not_there(self):
        self.t_plant.stop()
        cfg = copy.deepcopy(self.cfg)
        cfg["links"]["tdk"]["port"] = 1                      # nobody listens there
        plant = Plant(cfg)
        with self.assertLogs("mist2sim.plant", "INFO") as logs, PlantThread(plant):
            self.assertTrue(wait_until(lambda: plant.steps > 5, 3))
            self.assertFalse(plant.links["tdk"].up)
            self.assertTrue(plant.links["rek"].up)
            self.assertTrue(wait_until(lambda: values(self.ctl("rek"))["1.load_ohm"]["external"], 2))
        text = "\n".join(logs.output)
        self.assertIn("tdk not there yet", text)
        self.assertIn("released", text)
        self.assertFalse(values(self.ctl("rek"))["1.load_ohm"]["external"])


if __name__ == "__main__":
    unittest.main()
