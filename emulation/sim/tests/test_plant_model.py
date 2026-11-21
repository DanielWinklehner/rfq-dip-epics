"""The pure plant model: signs, limit cases, steady state, the filament lag, the configuration."""

import math
import os
import re
import unittest

import helpers  # noqa: F401  (sys.path)

from mist2sim.plant.model import (DISTURBANCES, INPUTS, PARAMETERS, PlantModel, idle_inputs,
                                  load_params, operating_point)

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "..", "config", "plant.yaml")
README = os.path.join(HERE, "..", "README.md")

# A working point: gas, valves open, pumps at speed, discharge 100 V, extraction on, cup in.
RUN = dict(idle_inputs(), filament_current=200.0, rek_vset=100.0, rek_iset=24.0, rek_on=1,
           gas_flow=5.0, shutoff_open=1, foreline_open=1, turbo1_speed=1, turbo2_speed=1,
           source_vset=15000.0, source_iset=0.015, source_on=1, puller_voltage=3000.0,
           puller_on=1, cup_in=1)


class ModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = load_params(CONFIG)
        cls.m = PlantModel(cls.params)

    def steady(self, seconds=40.0, state=None, **changes):
        inputs = dict(RUN, **changes)
        return self.m.settle(state or self.m.initial_state(), inputs, seconds, dt=0.02)

    # --- each relation: sign and limits --------------------------------------------------

    def test_filament(self):
        m = self.m
        self.assertAlmostEqual(m.filament_resistance(self.params["filament_t_hot_k"]),
                               self.params["filament_r_hot_ohm"])
        self.assertLess(m.filament_resistance(300.0), m.filament_resistance(2000.0))
        self.assertAlmostEqual(m.filament_equilibrium(0.0), self.params["room_temperature_k"])
        self.assertLess(m.filament_equilibrium(500.0), m.filament_equilibrium(1000.0))
        self.assertLess(m.emission(300.0), 1e-30)                           # cold: no emission
        self.assertGreater(m.emission(2700.0), 2 * m.emission(2600.0))      # steep
        _, cold = self.steady(filament_current=0.0)
        self.assertLess(cold["discharge_current"], 1e-12)
        self.assertAlmostEqual(cold["filament_temperature"], self.params["room_temperature_k"])
        a, b = self.steady(filament_current=190.0)[1], self.steady(filament_current=200.0)[1]
        for key in ("filament_temperature", "filament_resistance", "emission", "discharge_current"):
            self.assertGreater(b[key], a[key], key)

    def test_discharge_needs_voltage_gas_and_emission(self):
        _, out = self.steady()
        self.assertGreater(out["discharge_current"], 1.0)
        for changes in ({"rek_on": 0}, {"rek_vset": 20.0}, {"gas_flow": 0.0},
                        {"shutoff_open": 0}, {"filament_current": 0.0}):
            _, o = self.steady(**changes)
            self.assertLess(o["discharge_current"], 1e-12, changes)
            self.assertLess(o["beam_current"], 1e-15, changes)
        low, high = self.steady(rek_vset=60.0)[1], self.steady(rek_vset=120.0)[1]
        self.assertLess(low["discharge_current"], high["discharge_current"])
        lean, rich = self.steady(gas_flow=1.0)[1], self.steady(gas_flow=10.0)[1]
        self.assertLess(lean["discharge_current"], rich["discharge_current"])
        # emission limited at low filament power: the discharge carries about the emission
        _, o = self.steady(filament_current=180.0)
        self.assertAlmostEqual(o["discharge_current"] / o["emission"], 1.0, delta=0.02)
        # plasma limited at high filament power: more filament current changes little
        hot1, hot2 = self.steady(filament_current=260.0)[1], self.steady(filament_current=270.0)[1]
        self.assertLess(hot2["discharge_current"] - hot1["discharge_current"], 0.05)
        self.assertLess(hot1["discharge_current"], hot1["emission"] / 2)

    def test_discharge_supply_current_limit(self):
        _, free = self.steady()
        self.assertAlmostEqual(free["discharge_voltage"], 100.0)
        _, limited = self.steady(rek_iset=3.0)
        self.assertAlmostEqual(limited["rek_current"], 3.0, places=6)
        self.assertLess(limited["discharge_voltage"], 100.0)
        # what the REK simulator does with the load the plant gives it: CC at the same point
        r = limited["rek_load"]
        self.assertGreater(100.0 / r, 3.0)
        self.assertAlmostEqual(3.0 * r, limited["discharge_voltage"], places=6)
        # and in CV: V / R is the current
        self.assertAlmostEqual(100.0 / free["rek_load"], free["rek_current"], places=9)
        self.assertEqual(operating_point(100.0, 1.0, False, lambda v: v), (0.0, 0.0))

    def test_gas_and_vacuum(self):
        _, run = self.steady()
        _, base = self.steady(gas_flow=0.0)
        self.assertAlmostEqual(base["source_pressure"], self.params["source_base_torr"], delta=1e-8)
        self.assertAlmostEqual(base["diag_pressure"], self.params["diag_base_torr"], delta=1e-8)
        self.assertAlmostEqual(base["foreline_pressure"], self.params["foreline_base_torr"], delta=1e-5)
        for key in ("chamber_pressure", "source_pressure", "diag_pressure", "foreline_pressure"):
            self.assertGreater(run[key], base[key], key)
        self.assertGreater(run["chamber_pressure"], run["source_pressure"])
        self.assertGreater(run["source_pressure"], run["diag_pressure"])
        # shutoff valve closed: no flow, whatever the controller reports
        _, shut = self.steady(shutoff_open=0, gas_flow=50.0)
        self.assertEqual(shut["gas_into_source"], 0.0)
        self.assertAlmostEqual(shut["source_pressure"], base["source_pressure"], delta=1e-9)
        # a stopped pump: pressure up, much
        _, stopped = self.steady(turbo1_speed=0.0)
        self.assertGreater(stopped["source_pressure"], 10 * run["source_pressure"])
        _, stopped2 = self.steady(turbo2_speed=0.0)
        self.assertGreater(stopped2["diag_pressure"], 10 * run["diag_pressure"])
        # foreline valve closed: the foreline fills up
        s, o1 = self.steady(seconds=5.0, foreline_open=0)
        _, o2 = self.steady(seconds=5.0, state=s, foreline_open=0)
        self.assertGreater(o1["foreline_pressure"], run["foreline_pressure"])
        self.assertGreater(o2["foreline_pressure"], o1["foreline_pressure"])
        # vent: fast and high
        _, vented = self.steady(seconds=20.0, vent_open=1)
        self.assertGreater(vented["source_pressure"], 100.0)
        self.assertLessEqual(vented["foreline_pressure"], self.params["atmosphere_torr"])

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
        self.assertLess(hi, self.params["beam_fraction"] * o["discharge_current"] * 1.0001)
        # proportional to the discharge current
        a, b = self.steady(filament_current=195.0)[1], self.steady(filament_current=205.0)[1]
        self.assertAlmostEqual(a["beam_current"] / a["discharge_current"],
                               b["beam_current"] / b["discharge_current"], places=9)
        # the source supply's current limit
        _, lim = self.steady(source_iset=0.0005)
        self.assertAlmostEqual(lim["source_current"], 0.0005, places=9)
        self.assertLess(lim["source_voltage"], 15000.0)

    def test_heat(self):
        s0 = self.m.initial_state()
        _, cold = self.m.step(s0, idle_inputs(), 0.1)
        self.assertEqual(cold["thermocouples"], self.params["tc_base_c"])
        s, early = self.steady(seconds=5.0)
        _, late = self.steady(seconds=60.0, state=s)
        for k in self.params["tc_base_c"]:
            self.assertGreater(early["thermocouples"][k], self.params["tc_base_c"][k])
            self.assertGreater(late["thermocouples"][k], early["thermocouples"][k])
        for k in self.params["water_base_c"]:
            self.assertGreater(late["water_temperatures"][k], self.params["water_base_c"][k])
        # the water lags more than the thermocouples: a smaller part of its final rise after 5 s
        p = self.params
        k_water = p["water_heat_fraction"] / (p["water_flow_l_min"] / 60.0 * p["water_cp_j_per_kg_k"])
        tc_part = (early["thermocouples"]["t1"] - p["tc_base_c"]["t1"]) / (p["tc_gain_k_per_w"] * late["heat_power"])
        water_part = (early["water_temperatures"]["t1"] - p["water_base_c"]["t1"]) / (k_water * late["heat_power"])
        self.assertGreater(tc_part, water_part)
        self.assertLess(tc_part, 0.5)

    # --- global properties --------------------------------------------------------------

    def test_never_negative_and_finite(self):
        m = self.m
        state = m.initial_state()
        seq = [RUN, dict(RUN, vent_open=1), dict(RUN, turbo1_speed=0, rek_iset=0.0),
               dict(RUN, filament_current=300.0), idle_inputs(), dict(RUN, foreline_open=0),
               dict(RUN, gas_flow=-5.0, filament_current=-10.0, puller_voltage=-100.0)]
        for inputs in seq:
            for _ in range(200):
                state, out = m.step(state, inputs, 0.1)
                for k, v in out.items():
                    for x in (v.values() if isinstance(v, dict) else [v]):
                        self.assertTrue(math.isfinite(x), k)
                        if k not in ("thermocouples", "water_temperatures"):
                            self.assertGreaterEqual(x, 0.0, k)
                for k in ("filament_temperature", "chamber_pressure", "source_pressure",
                          "diag_pressure", "foreline_pressure", "tc_power", "water_power"):
                    self.assertGreaterEqual(state[k], 0.0, k)

    def test_pure_and_deterministic(self):
        s0 = self.m.initial_state()
        copy = dict(s0)
        a = self.m.step(s0, RUN, 0.1)
        b = self.m.step(s0, RUN, 0.1)
        self.assertEqual(s0, copy)
        self.assertEqual(a, b)
        # one big step and many small ones end at about the same place (exact lags)
        big = self.m.step(s0, dict(RUN, filament_current=0.0, gas_flow=10.0), 1.0)[1]
        small = self.m.settle(s0, dict(RUN, filament_current=0.0, gas_flow=10.0), 1.0, dt=0.001)[1]
        self.assertAlmostEqual(big["chamber_pressure"] / small["chamber_pressure"], 1.0, delta=0.15)

    def test_steady_state_exists(self):
        s, a = self.steady(seconds=60.0)
        _, b = self.steady(seconds=10.0, state=s)
        for k in ("filament_temperature", "discharge_current", "source_pressure", "diag_pressure",
                  "foreline_pressure", "beam_current"):
            self.assertAlmostEqual(a[k] / b[k], 1.0, delta=1e-4, msg=k)

    def test_filament_step_settles_with_the_configured_lag(self):
        """A small step of the filament current: the discharge current settles first-order. At
        constant current the resistance rises with T (R ~ T^x), the radiation goes with T^4, so
        the lag at the working point is tau / (1 - x / 4) (Stefan-Boltzmann with T_room << T)."""
        tau = self.params["filament_tau_s"]
        expected = tau / (1.0 - self.params["filament_r_exponent"] / 4.0)
        dt = 0.005
        s, before = self.steady(seconds=60.0)
        inputs = dict(RUN, filament_current=201.0)
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
        # settled after five lags
        s2, _ = self.steady(seconds=60.0)
        _, o5 = self.m.settle(s2, inputs, 5 * expected, dt)
        self.assertAlmostEqual(o5["discharge_current"], after["discharge_current"],
                               delta=0.02 * (after["discharge_current"] - before["discharge_current"]))

    def test_disturbances(self):
        s, base = self.steady()
        s1 = dict(s, emission_factor=0.9)
        _, o = self.m.settle(s1, RUN, 0.1)
        self.assertLess(o["emission"], base["emission"])
        s2 = dict(s, emission_drift_per_min=-0.1)
        s2, _ = self.m.settle(s2, RUN, 60.0, dt=0.1)
        self.assertAlmostEqual(s2["emission_factor"], math.exp(-0.1), delta=0.002)
        s3 = dict(s, pressure_burst_sccm=20.0)
        s3, o3 = self.m.settle(s3, RUN, 0.5)
        self.assertGreater(o3["source_pressure"], 1.5 * base["source_pressure"])
        _, o4 = self.m.settle(s3, RUN, 30.0)
        self.assertAlmostEqual(o4["source_pressure"] / base["source_pressure"], 1.0, delta=0.01)
        self.assertEqual(set(DISTURBANCES) - set(s), set())


class ConfigTest(unittest.TestCase):
    def test_every_parameter_documented(self):
        import yaml
        with open(CONFIG) as f:
            model = yaml.safe_load(f)["model"]
        self.assertEqual(set(model), set(PARAMETERS))
        for name, entry in model.items():
            self.assertTrue(entry["unit"], name)
            self.assertRegex(entry["source"], r"^(law|estimate|free choice)", name)
        with open(README) as f:
            text = f.read()
        table = re.findall(r"^\| `(\w+)` \|", text, re.M)
        self.assertEqual(sorted(set(PARAMETERS) - set(table)), [], "parameters missing in README.md")
        for name in INPUTS:
            self.assertIn(name, text)

    def test_bad_parameters(self):
        from mist2sim.plant.model import params_from
        with self.assertRaises(ValueError):
            params_from({"filament_tau_s": 1.0})
        with self.assertRaises(ValueError):
            params_from({"filament_tau_s": {"value": 1.0, "unit": "s", "source": "x"}})


if __name__ == "__main__":
    unittest.main()
