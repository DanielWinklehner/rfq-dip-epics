"""The pure plant model (phase 1: one cross, one turbopump, both gauges on the cross): signs,
limit cases, the owner's working point, steady state, the filament lag, the configuration."""

import math
import os
import re
import unittest

import helpers  # noqa: F401  (sys.path)

from mist2sim.plant.model import (DISTURBANCES, INPUTS, PARAMETERS, PlantModel, idle_inputs,
                                  load_params, operating_point, params_from,
                                  working_point_inputs)

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "..", "config", "plant.yaml")
README = os.path.join(HERE, "..", "README.md")


class ModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = load_params(CONFIG)
        cls.m = PlantModel(cls.params)
        # the owner's working point, the REK limit opened a little so that the discharge is not
        # held by it, plus extraction on and the cup in
        cls.inp = dict(working_point_inputs(cls.params), rek_iset=30.0, filament_current=88.0,
                       source_vset=15000.0, source_iset=0.015, source_on=1,
                       puller_voltage=3000.0, puller_on=1, cup_in=1)

    def steady(self, seconds=40.0, state=None, **changes):
        inputs = dict(self.inp, **changes)
        return self.m.settle(state or self.m.initial_state(), inputs, seconds, dt=0.02)

    # --- the owner's working point ------------------------------------------------------

    def test_working_point(self):
        """8 V at 90 A on the filament, 24 A at 150 V on the discharge: reproduced within 10 %.
        The pressure is predicted: the reading the documented pumping speed gives."""
        p, d = self.params, self.m.derived
        _, o = self.m.settle(self.m.initial_state(), working_point_inputs(p), 60.0, dt=0.02)
        checks = {"filament_voltage": 8.0, "discharge_current": 24.0, "discharge_voltage": 150.0,
                  "gas_into_source": 1.0}
        for key, want in checks.items():
            self.assertAlmostEqual(o[key] / want, 1.0, delta=0.10, msg=key)
        self.assertAlmostEqual(o["filament_power"], 720.0, delta=72.0)
        # the pressure: what 1 sccm H2 and the data sheet pumping speed give, nothing else
        self.assertAlmostEqual(d["turbo_speed_l_s"], p["turbo_speed_n2_l_s"] * p["turbo_h2_n2_ratio"])
        true = (d["outgassing_torr_l_s"] + p["wp_gas_sccm"] * p["sccm_to_torr_l_s"]) / d["turbo_speed_l_s"]
        self.assertAlmostEqual(d["cross_wp_torr"] / true, 1.0, delta=0.01)   # p_lim fall-off < 1 %
        self.assertAlmostEqual(o["aim_reading"] / d["aim_wp_reading_torr"], 1.0, delta=0.01)
        self.assertAlmostEqual(o["aim_reading"], p["aim_h2_factor"] * true, delta=0.02 * o["aim_reading"])
        # the REK is at its current limit there: 24 A is its full scale
        self.assertAlmostEqual(o["rek_current"], 24.0, places=3)
        # the APG cannot see 1e-5 torr: it shows its floor
        self.assertEqual(o["apg_reading"], p["apg_floor_torr"])

    def test_calibration_is_plausible(self):
        d = self.m.derived
        self.assertAlmostEqual(d["filament_r_hot_ohm"], 8.0 / 90.0)
        self.assertTrue(2400 < d["filament_t_hot_k"] < 3200, d["filament_t_hot_k"])
        self.assertTrue(0.5 < d["wire_diameter_mm"] < 3.0, d["wire_diameter_mm"])
        self.assertTrue(5 < d["wire_length_cm"] < 40, d["wire_length_cm"])
        self.assertTrue(100 < d["turbo_speed_l_s"] < 3000, d["turbo_speed_l_s"])

    # --- each relation: sign and limits --------------------------------------------------

    def test_filament(self):
        m, d = self.m, self.m.derived
        self.assertAlmostEqual(m.filament_resistance(d["filament_t_hot_k"]), d["filament_r_hot_ohm"])
        self.assertLess(m.filament_resistance(300.0), m.filament_resistance(2000.0))
        self.assertAlmostEqual(m.filament_equilibrium(0.0), self.params["room_temperature_k"])
        self.assertLess(m.filament_equilibrium(300.0), m.filament_equilibrium(700.0))
        self.assertLess(m.emission(300.0), 1e-30)                           # cold: no emission
        self.assertGreater(m.emission(2900.0), 2 * m.emission(2800.0))      # steep
        _, cold = self.steady(filament_current=0.0)
        self.assertLess(cold["discharge_current"], 1e-12)
        self.assertAlmostEqual(cold["filament_temperature"], self.params["room_temperature_k"])
        a, b = self.steady(filament_current=84.0)[1], self.steady(filament_current=87.0)[1]
        for key in ("filament_temperature", "filament_resistance", "filament_voltage", "emission",
                    "discharge_current"):
            self.assertGreater(b[key], a[key], key)

    def test_discharge_needs_voltage_gas_and_emission(self):
        _, out = self.steady()
        self.assertGreater(out["discharge_current"], 1.0)
        for changes in ({"rek_on": 0}, {"rek_vset": 20.0}, {"gas_flow": 0.0},
                        {"shutoff_open": 0}, {"filament_current": 0.0}):
            _, o = self.steady(**changes)
            self.assertLess(o["discharge_current"], 1e-12, changes)
            self.assertLess(o["beam_current"], 1e-15, changes)
        # emission limited around the working point: the discharge carries about the emission
        self.assertAlmostEqual(out["discharge_current"] / out["emission"], 1.0, delta=0.05)
        # plasma limited at high filament power (REK limit open): more filament current changes little
        hot1 = self.steady(filament_current=110.0, rek_iset=100.0)[1]
        hot2 = self.steady(filament_current=115.0, rek_iset=100.0)[1]
        self.assertLess(hot2["discharge_current"] - hot1["discharge_current"], 0.5)
        self.assertLess(hot1["discharge_current"], hot1["emission"] / 2)
        # voltage and gas raise the plasma limit
        lo, hi = (self.steady(filament_current=110.0, rek_iset=100.0, rek_vset=v)[1] for v in (100.0, 150.0))
        self.assertLess(lo["discharge_current"], hi["discharge_current"])
        lean, rich = (self.steady(filament_current=110.0, rek_iset=100.0, gas_flow=g)[1] for g in (0.5, 2.0))
        self.assertLess(lean["discharge_current"], rich["discharge_current"])

    def test_discharge_supply_current_limit(self):
        _, free = self.steady()
        self.assertAlmostEqual(free["discharge_voltage"], 150.0)
        _, limited = self.steady(rek_iset=5.0)
        self.assertAlmostEqual(limited["rek_current"], 5.0, places=6)
        self.assertLess(limited["discharge_voltage"], 150.0)
        # what the REK simulator does with the load the plant gives it: CC at the same point
        r = limited["rek_load"]
        self.assertGreater(150.0 / r, 5.0)
        self.assertAlmostEqual(5.0 * r, limited["discharge_voltage"], places=6)
        self.assertAlmostEqual(150.0 / free["rek_load"], free["rek_current"], places=9)
        self.assertEqual(operating_point(100.0, 1.0, False, lambda v: v), (0.0, 0.0))
        # above the working point, at the owner's limit of 24 A, the current stays at 24 A
        _, wp_up = self.m.settle(self.m.initial_state(),
                                 dict(working_point_inputs(self.params), filament_current=95.0), 40.0, 0.02)
        self.assertAlmostEqual(wp_up["rek_current"], 24.0, places=3)
        self.assertLess(wp_up["discharge_voltage"], 150.0)

    def test_gas_and_vacuum(self):
        p, d = self.params, self.m.derived
        _, run = self.steady()
        _, base = self.steady(gas_flow=0.0)
        self.assertAlmostEqual(base["aim_reading"], p["cross_base_reading_torr"], delta=1e-8)
        self.assertAlmostEqual(base["foreline_pressure"], p["foreline_base_torr"], delta=1e-5)
        for key in ("chamber_pressure", "cross_pressure", "aim_reading", "foreline_pressure"):
            self.assertGreater(run[key], base[key], key)
        self.assertGreater(run["chamber_pressure"], run["cross_pressure"])
        self.assertLess(run["aim_reading"], run["cross_pressure"])       # nAIM reads H2 low
        # shutoff valve closed: no flow, whatever the controller reports
        _, shut = self.steady(shutoff_open=0, gas_flow=5.0)
        self.assertEqual(shut["gas_into_source"], 0.0)
        self.assertAlmostEqual(shut["cross_pressure"], base["cross_pressure"], delta=1e-10)
        # the pump stopped: pressure up, much; the APG sees it once above its floor
        _, stopped = self.steady(turbo_speed=0.0)
        self.assertGreater(stopped["cross_pressure"], 10 * run["cross_pressure"])
        self.assertGreater(stopped["apg_reading"], p["apg_floor_torr"])
        self.assertEqual(run["apg_reading"], p["apg_floor_torr"])
        self.assertLess(self.steady(turbo_speed=0.5)[1]["cross_pressure"], stopped["cross_pressure"])
        # foreline valve closed: the foreline fills up
        s, o1 = self.steady(seconds=5.0, foreline_open=0)
        _, o2 = self.steady(seconds=5.0, state=s, foreline_open=0)
        self.assertGreater(o1["foreline_pressure"], run["foreline_pressure"])
        self.assertGreater(o2["foreline_pressure"], o1["foreline_pressure"])
        # vent valve: vents the turbopump (foreline side) fast, the cross only a little
        _, vented = self.steady(seconds=30.0, vent_open=1)
        self.assertGreater(vented["foreline_pressure"], 10.0)
        self.assertGreater(vented["cross_pressure"], run["cross_pressure"])
        self.assertLess(vented["cross_pressure"], 3 * run["cross_pressure"])
        _, vented_closed = self.steady(seconds=60.0, vent_open=1, foreline_open=0)
        self.assertAlmostEqual(vented_closed["foreline_pressure"], p["atmosphere_torr"], delta=1.0)
        self.assertLess(vented_closed["cross_pressure"], 1e-3)
        self.assertGreater(d["turbo_speed_l_s"], 0)

    def test_extraction_and_cup(self):
        _, o = self.steady()
        self.assertGreater(o["beam_current"], 0.0)
        self.assertEqual(o["cup_current"], o["beam_current"])
        self.assertAlmostEqual(o["source_current"],
                               o["beam_current"] + o["source_voltage"] / self.params["source_leak_ohm"])
        self.assertAlmostEqual(o["source_voltage"] / o["source_load"], o["source_current"])
        self.assertEqual(self.steady(cup_in=0)[1]["cup_current"], 0.0)
        for changes in ({"source_on": 0}, {"puller_on": 0}):
            self.assertEqual(self.steady(**changes)[1]["beam_current"], 0.0, changes)
        lo, mid, hi = (self.steady(source_vset=v)[1]["beam_current"] for v in (2000.0, 10000.0, 18000.0))
        self.assertLess(lo, mid)
        self.assertLess(hi - mid, mid - lo)                     # saturating
        a, b = self.steady(filament_current=84.0)[1], self.steady(filament_current=87.0)[1]
        self.assertAlmostEqual(a["beam_current"] / a["discharge_current"],
                               b["beam_current"] / b["discharge_current"], places=9)
        _, lim = self.steady(source_iset=0.0015)
        self.assertAlmostEqual(lim["source_current"], 0.0015, places=9)
        self.assertLess(lim["source_voltage"], 15000.0)

    def test_heat(self):
        p = self.params
        _, cold = self.m.step(self.m.initial_state(), idle_inputs(), 0.1)
        self.assertEqual(cold["back_plate_temperature"], p["back_plate_base_c"])
        self.assertEqual(cold["transformer1_temperature"], p["transformer1_base_c"])
        s, early = self.steady(seconds=5.0)
        _, late = self.steady(seconds=300.0, state=s)
        for k in ("back_plate_temperature", "feedthrough_temperature", "transformer1_temperature",
                  "transformer2_temperature"):
            self.assertGreater(early[k], cold[k], k)
            self.assertGreater(late[k], early[k], k)
        self.assertAlmostEqual(late["back_plate_temperature"] - p["back_plate_base_c"],
                               p["back_plate_k_per_w"] * late["heat_power"], delta=0.01)
        # the feedthrough and transformer 1 follow the filament power, not the plasma
        _, no_plasma = self.steady(seconds=300.0, rek_on=0)
        self.assertAlmostEqual(no_plasma["feedthrough_temperature"], late["feedthrough_temperature"], delta=0.01)
        self.assertAlmostEqual(no_plasma["transformer1_temperature"], late["transformer1_temperature"], delta=0.01)
        self.assertLess(no_plasma["back_plate_temperature"], late["back_plate_temperature"])
        self.assertAlmostEqual(no_plasma["transformer2_temperature"], p["transformer2_base_c"], delta=0.01)
        # transformer 2 warms with the square of what the REK delivers
        rise = late["transformer2_temperature"] - p["transformer2_base_c"]
        self.assertAlmostEqual(rise, p["transformer_rise_k"] * (late["discharge_voltage"] * late["rek_current"]
                                                                / p["transformer2_rated_w"]) ** 2, delta=0.02 * rise)
        for k in p["water_base_c"]:
            self.assertGreater(late["water_temperatures"][k], p["water_base_c"][k])

    # --- global properties --------------------------------------------------------------

    def test_never_negative_and_finite(self):
        m = self.m
        state = m.initial_state()
        run = self.inp
        seq = [run, dict(run, vent_open=1), dict(run, turbo_speed=0, rek_iset=0.0),
               dict(run, filament_current=300.0), idle_inputs(), dict(run, foreline_open=0, vent_open=1),
               dict(run, gas_flow=-5.0, filament_current=-10.0, puller_voltage=-100.0)]
        for inputs in seq:
            for _ in range(200):
                state, out = m.step(state, inputs, 0.1)
                for k, v in out.items():
                    for x in (v.values() if isinstance(v, dict) else [v]):
                        self.assertTrue(math.isfinite(x), k)
                        self.assertGreaterEqual(x, 0.0, k)
                for k in ("filament_temperature", "chamber_pressure", "cross_pressure",
                          "foreline_pressure", "plate_power", "water_power"):
                    self.assertGreaterEqual(state[k], 0.0, k)

    def test_pure_and_deterministic(self):
        s0 = self.m.initial_state()
        copy = dict(s0)
        a = self.m.step(s0, self.inp, 0.1)
        b = self.m.step(s0, self.inp, 0.1)
        self.assertEqual(s0, copy)
        self.assertEqual(a, b)
        big = self.m.step(s0, dict(self.inp, filament_current=0.0, gas_flow=3.0), 1.0)[1]
        small = self.m.settle(s0, dict(self.inp, filament_current=0.0, gas_flow=3.0), 1.0, dt=0.001)[1]
        self.assertAlmostEqual(big["chamber_pressure"] / small["chamber_pressure"], 1.0, delta=0.15)

    def test_steady_state_exists(self):
        s, a = self.steady(seconds=60.0)
        _, b = self.steady(seconds=10.0, state=s)
        for k in ("filament_temperature", "discharge_current", "cross_pressure",
                  "foreline_pressure", "beam_current"):
            self.assertAlmostEqual(a[k] / b[k], 1.0, delta=1e-4, msg=k)

    def test_filament_step_settles_with_the_configured_lag(self):
        """A small step of the filament current below the working point: the discharge current
        settles first-order with tau / (1 - x / 4) (R ~ T^x at constant current, radiation ~ T^4)."""
        tau = self.params["filament_tau_s"]
        expected = tau / (1.0 - self.params["filament_r_exponent"] / 4.0)
        dt = 0.005
        s, before = self.steady(seconds=60.0)
        inputs = dict(self.inp, filament_current=self.inp["filament_current"] + 0.2)
        _, after = self.m.settle(s, inputs, 60.0)
        target = before["discharge_current"] + 0.632 * (after["discharge_current"] - before["discharge_current"])
        t = 0.0
        while True:
            s, o = self.m.step(s, inputs, dt)
            t += dt
            if o["discharge_current"] >= target:
                break
        self.assertGreater(after["discharge_current"], before["discharge_current"])
        self.assertAlmostEqual(t / expected, 1.0, delta=0.1)
        s2, _ = self.steady(seconds=60.0)
        _, o5 = self.m.settle(s2, inputs, 5 * expected, dt)
        self.assertAlmostEqual(o5["discharge_current"], after["discharge_current"],
                               delta=0.02 * (after["discharge_current"] - before["discharge_current"]))

    def test_disturbances(self):
        s, base = self.steady()
        _, o = self.m.settle(dict(s, emission_factor=0.9), self.inp, 0.1)
        self.assertLess(o["emission"], base["emission"])
        s2, _ = self.m.settle(dict(s, emission_drift_per_min=-0.1), self.inp, 60.0, dt=0.1)
        self.assertAlmostEqual(s2["emission_factor"], math.exp(-0.1), delta=0.002)
        s3, o3 = self.m.settle(dict(s, pressure_burst_sccm=2.0), self.inp, 0.5)
        self.assertGreater(o3["cross_pressure"], 1.5 * base["cross_pressure"])
        _, o4 = self.m.settle(s3, self.inp, 30.0)
        self.assertAlmostEqual(o4["cross_pressure"] / base["cross_pressure"], 1.0, delta=0.01)
        self.assertEqual(set(DISTURBANCES) - set(s), set())


class ConfigTest(unittest.TestCase):
    def test_every_parameter_documented(self):
        import yaml
        with open(CONFIG) as f:
            cfg = yaml.safe_load(f)
        model = cfg["model"]
        self.assertEqual(set(model), set(PARAMETERS))
        for name, entry in model.items():
            self.assertTrue(entry["unit"], name)
            self.assertRegex(entry["source"], r"^(law|estimate|free choice|owner's working point, 2026-11-21)", name)
            if name.startswith("wp_"):
                self.assertTrue(entry["source"].startswith("owner's working point, 2026-11-21"), name)
        with open(README) as f:
            text = f.read()
        table = re.findall(r"^\| `(\w+)` \|", text, re.M)
        self.assertEqual(sorted(set(PARAMETERS) - set(table)), [], "parameters missing in README.md")
        for name in INPUTS:
            self.assertIn(name, text)
        # phase 1: no turbopump 2, no diagnostic box gauge
        self.assertNotIn("nt20_2", cfg["links"])
        self.assertNotIn("gauges.p2", cfg["outputs"])

    def test_gas_scale_matches_the_mfc(self):
        import yaml
        from mist2sim.core import load_config
        with open(CONFIG) as f:
            cfg = yaml.safe_load(f)
        mfc = [e for e in load_config(os.path.join(HERE, "..", "config", "rack.yaml")) if e["name"] == "mfc"][0]
        full_scale = mfc["options"]["units"][0]["full_scale"]
        self.assertAlmostEqual(cfg["inputs"]["gas_flow"]["scale"] * 100.0, full_scale)

    def test_turbo_scale_matches_the_rated_speed(self):
        import yaml
        from mist2sim.core import load_config
        with open(CONFIG) as f:
            cfg = yaml.safe_load(f)
        pump = [e for e in load_config(os.path.join(HERE, "..", "config", "rack.yaml")) if e["name"] == "nt20_1"][0]
        self.assertAlmostEqual(cfg["inputs"]["turbo_speed"]["scale"] * pump["options"]["rated_speed_hz"], 1.0, places=6)

    def test_bad_parameters(self):
        with self.assertRaises(ValueError):
            params_from({"filament_tau_s": 1.0})
        with self.assertRaises(ValueError):
            params_from({"filament_tau_s": {"value": 1.0, "unit": "s", "source": "x"}})


if __name__ == "__main__":
    unittest.main()
