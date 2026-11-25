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
RESTARTED = "tic"           # this one runs in its own thread, to be stopped and started again


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
        cfg["model"]["plate_tau_s"]["value"] = 1.0    # see a temperature move within a second
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
        self.assertTrue(wait_until(lambda: values(self.ctl("tic"))["g2.pressure"]["external"], 3))
        aim = lambda: values(self.ctl("tic"), "g2.pressure")[0]   # noqa: E731  the AIM on TIC socket 2
        base_t1 = values(self.ctl("thermocouple"), "t1")[0]
        # phase 1: nothing drives the nAIM (deferred), TIC socket 3 (empty) or turbopump 2
        self.assertFalse(values(self.ctl("aim"))["pressure"]["external"])
        self.assertFalse(values(self.ctl("tic"))["g3.pressure"]["external"])
        self.assertNotIn("aim", self.plant.links)
        self.assertNotIn("nt20_2", self.plant.links)
        # the foreline gauge (VGC401) reads the model's foreline pressure
        self.assertTrue(wait_until(lambda: values(self.ctl("vgc401"))["pressure"]["external"], 3))
        self.assertAlmostEqual(values(self.ctl("vgc401"), "pressure")[0] / self.plant_get("foreline_pressure"), 1, delta=0.05)
        # the pump is not running: the pressure in the cross rises from the base pressure
        self.assertTrue(wait_until(lambda: aim() > 2e-5, 6))

        # turbopump 1: run relay on the turbopump Opta, fast run-up
        self.device("turbo_opta", "Sr11")
        self.assertTrue(wait_until(lambda: values(self.ctl("nt20_1"), "speed")[0] >= 0.999 * self.sims["nt20_1"].options["rated_speed_hz"], 5))
        self.assertTrue(wait_until(lambda: aim() < 2.2e-6, 5))
        pumped = aim()
        self.assertAlmostEqual(pumped, 2.0e-6, delta=2e-7)
        # the APG on the cross reports exactly its floor at high vacuum, and the AIM is on
        self.assertLess(values(self.ctl("tic"), "g1.pressure")[0], 1e-5)
        self.assertEqual(self.device("tic", "?V913")[0], [b"=V913 1.0000e-02;59;11;0;0"])
        self.assertTrue(wait_until(lambda: self.device("tic", "?V914")[0][0].split(b";")[2] == b"11", 5))

        # gas: MFC 20 % of 5 sccm, shutoff valve still closed: no change
        self.device("mfc", "@@@254S!20")
        time.sleep(1.5)
        self.assertAlmostEqual(aim(), pumped, delta=2e-7)
        # foreline valve and shutoff valve open: the cross goes to the predicted reading
        self.device("valvebox", "Ss11", "Ss21")
        predicted = self.plant.model.derived["aim_wp_reading_torr"]
        self.assertTrue(wait_until(lambda: abs(aim() / predicted - 1) < 0.1, 4))
        self.assertGreater(self.plant_get("foreline_pressure"), 3e-2)

        # the owner's working point: filament 8 V / 90 A, discharge 150 V with the limit at 24 A
        self.device("tdk", "ADR 6", "PV 8", "PC 90", "OUT 1")
        self.device("rek", "#1 REN", "#1 VCN 100", "#1 ICN 100", "#1 SW1")
        self.assertTrue(wait_until(lambda: values(self.ctl("rek"), "1.iout")[0] > 21.6, 10))
        self.assertAlmostEqual(values(self.ctl("tdk"), "load_ohm")[0], 8.0 / 90.0, delta=0.005)
        self.assertAlmostEqual(values(self.ctl("tdk"), "mv")[0], 8.0, delta=0.4)
        # the REK's own current limit still works: 10 A
        self.device("rek", "#1 ICN 41.67")
        self.assertTrue(wait_until(lambda: abs(values(self.ctl("rek"), "1.iout")[0] - 10.0) < 0.05, 3))
        self.assertLess(values(self.ctl("rek"), "1.vout")[0], 149.0)
        self.device("rek", "#1 ICN 100")

        # extraction: source 15 kV, puller 3 kV, cup out: nothing on the cup; cup in: beam
        self.device("mat_opt", "#1 REN", "#1 VCN 75", "#1 ICN 100", "#1 SW1",
                    "#2 REN", "#2 VCN 15", "#2 ICN 100", "#2 SW1")
        self.assertTrue(wait_until(lambda: self.plant_get("beam_current") > 1e-4, 3))
        self.assertEqual(values(self.ctl("faradaycup"), "i1")[0], 0.0)
        self.device("valvebox", "Ss41")
        self.assertTrue(wait_until(lambda: values(self.ctl("faradaycup"), "i1")[0] > 1e-4, 3))
        # the source supply delivers beam plus leakage
        self.assertTrue(wait_until(lambda: abs(values(self.ctl("mat_opt"), "1.iout")[0]
                                               / self.plant_get("source_current") - 1) < 0.02, 3))
        with ControlClient("127.0.0.1", self.plant.control_port) as c:
            sig = c.get()["signals"]
        self.assertGreater(sig["source_current"]["value"], sig["beam_current"]["value"])

        # a temperature responds (back plate)
        self.assertTrue(wait_until(lambda: values(self.ctl("thermocouple"), "t1")[0] > base_t1 + 3, 4))

        # the vent valve vents the turbopump: the foreline fills, the cross rises only a little
        before = aim()
        self.device("valvebox", "Ss31")
        self.assertTrue(wait_until(lambda: self.plant_get("foreline_pressure") > 10.0, 3))
        self.assertTrue(wait_until(lambda: aim() > 1.03 * before, 3))
        self.assertLess(aim(), 2 * before)
        self.device("valvebox", "Ss30")

        # a disturbance through the plant's control port: emission drops, discharge follows
        i_before = values(self.ctl("rek"), "1.iout")[0]
        with ControlClient("127.0.0.1", self.plant.control_port) as c:
            c.set("emission_factor", 0.5)
            info = c.info()
            self.assertIn("filament_temperature", info["signals"])
            self.assertIn("foreline_pressure", info["signals"])
            self.assertIn("turbo_speed_l_s", info["derived"])
        self.assertTrue(wait_until(lambda: values(self.ctl("rek"), "1.iout")[0] < 0.8 * i_before, 3))
        with ControlClient("127.0.0.1", self.plant.control_port) as c:
            c.release("emission_factor")
            c.set("pressure_burst_sccm", 2.0)
            self.assertTrue(wait_until(lambda: c.get("pressure_burst_sccm")["value"] < 2.0, 2))

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
        self.assertTrue(wait_until(lambda: values(self.ctl("tic"))["g2.pressure"]["external"], 2))
        self.assertGreater(aim(), 1.03 * pumped)

        # stop the plant: every signal back to the device's own behaviour
        self.t_plant.stop()
        for target in self.cfg["outputs"]:
            sim, sig = split_signal(target)
            self.assertFalse(values(self.ctl(sim))[sig]["external"], target)
        self.assertEqual(values(self.ctl("tdk"), "load_ohm")[0], 0.089)
        self.assertEqual(values(self.ctl("rek"), "1.load_ohm")[0], 5.0)
        self.assertEqual(values(self.ctl("faradaycup"), "i1")[0], 1.0e-6)
        self.assertEqual(values(self.ctl("thermocouple"), "t1")[0], 41.0)
        self.assertEqual(values(self.ctl("tic"), "g1.pressure")[0], 4.3e-6)
        self.assertEqual(values(self.ctl("vgc401"), "pressure")[0], 0.03)
        self.assertEqual(aim(), 2.0e-6)

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
