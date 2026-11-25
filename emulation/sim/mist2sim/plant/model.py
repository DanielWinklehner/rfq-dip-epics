"""The MIST-2 plant model (phase 1): a pure, deterministic step function, no I/O, no clock.

    from mist2sim.plant.model import PlantModel, load_params, idle_inputs
    m = PlantModel(load_params("config/plant.yaml"))
    state = m.initial_state()
    state, out = m.step(state, dict(idle_inputs(), filament_current=90.0), 0.1)

The machine: ion source with a hairpin filament on the high-voltage platform, a high-voltage
break, ONE vacuum chamber at ground (a CF 10" six-way cross) with ONE turbopump on its bottom
flange. The APG and the AIM on the TIC station both measure the cross (owner, 2026-11-25); the
foreline gauge on the VGC401 measures the foreline. The vent valve vents the turbopump (and through
it, a little, the cross). See README.md, section "Plant model", for the equations.

Calibration: the owner's working point (parameters wp_*) fixes the hot filament resistance, the
filament temperature and area and the plasma limit. The pumping speed comes from the data sheet
of the turbopump, so the pressure at the working point is a PREDICTION (`derived`), compared with
the owner's range. PlantModel computes all this at construction.

`step` never changes the state it is given; it returns a new one. Units: SI except pressures
(torr, as the gauges), flows (sccm) and sensor temperatures (deg C).
"""

import math

import yaml

K_BOLTZMANN_EV = 8.617333e-5      # eV/K
SIGMA_SB = 5.670374e-8            # W/(m^2 K^4)

# Inputs of step(). Booleans are given as numbers (>= 0.5 means true), as the simulators have them.
INPUTS = {
    "filament_current": "A, measured by the TDK supply",
    "rek_vset": "V, discharge supply voltage set point",
    "rek_iset": "A, discharge supply current limit",
    "rek_on": "0/1, discharge supply output on",
    "gas_flow": "sccm, as the mass flow controller measures it",
    "shutoff_open": "0/1, MFC shutoff valve",
    "foreline_open": "0/1, foreline valve",
    "vent_open": "0/1, vent valve (vents the turbopump)",
    "cup_in": "0/1, Faraday cup moved in",
    "turbo_speed": "fraction of the rated speed of the turbopump on the cross",
    "source_vset": "V, source (extraction) supply set point",
    "source_iset": "A, source supply current limit",
    "source_on": "0/1, source supply output on",
    "puller_voltage": "V, magnitude of the puller supply output",
    "puller_on": "0/1, puller supply output on",
}

# The disturbances kept in the state, with their neutral values (set through the plant's
# control port, see process.py).
DISTURBANCES = {
    "emission_factor": 1.0,          # multiplies the emission
    "emission_drift_per_min": 0.0,   # relative change of emission_factor per minute
    "pressure_burst_sccm": 0.0,      # extra gas into the source, decays with burst_tau_s
}


def idle_inputs():
    """Everything off, valves closed, pump stopped."""
    return {k: 0.0 for k in INPUTS}


def working_point_inputs(p):
    """The model inputs of the owner's working point: TDK at wp current, REK at wp voltage
    with its limit at wp current (24 A, its full scale), gas at wp flow, valves open, pump at
    speed, extraction off."""
    return dict(idle_inputs(), filament_current=p["wp_filament_current_a"],
                rek_vset=p["wp_discharge_voltage_v"], rek_iset=p["wp_discharge_current_a"],
                rek_on=1, gas_flow=p["wp_gas_sccm"], shutoff_open=1, foreline_open=1,
                turbo_speed=1)


def load_params(path):
    """The `model` section of a plant configuration: {name: value}. Each entry in the file is
    {value, unit, source}; only the value is used here."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return params_from(data["model"])


def params_from(section):
    out = {}
    for name, entry in section.items():
        if not isinstance(entry, dict) or set(entry) != {"value", "unit", "source"}:
            raise ValueError("model parameter %r: expected {value, unit, source}" % name)
        out[name] = entry["value"]
    missing = sorted(set(PARAMETERS) - set(out))
    unknown = sorted(set(out) - set(PARAMETERS))
    if missing or unknown:
        raise ValueError("model parameters: missing %s, unknown %s" % (missing, unknown))
    return out


# Every parameter the model uses. The values, units and sources are in config/plant.yaml.
PARAMETERS = (
    "wp_filament_voltage_v", "wp_filament_current_a", "wp_discharge_voltage_v",
    "wp_discharge_current_a", "wp_cross_reading_low_torr", "wp_cross_reading_high_torr",
    "wp_gas_sccm", "turbo_speed_n2_l_s", "turbo_h2_n2_ratio",
    "filament_tau_s", "filament_r_exponent", "filament_emissivity", "room_temperature_k",
    "richardson_a_per_cm2_k2", "work_function_ev",
    "discharge_v_min_v", "discharge_exponent", "discharge_p_min_torr", "discharge_p_half_torr",
    "discharge_smooth_n", "plasma_margin", "rek_bleed_ohm",
    "sccm_to_torr_l_s", "aperture_conductance_l_s", "chamber_volume_l", "cross_volume_l",
    "aim_h2_factor", "cross_base_reading_torr", "apg_floor_torr", "apg_ceiling_torr",
    "turbo_stopped_fraction", "turbo_p_limit_torr",
    "foreline_base_torr", "foreline_volume_l", "rough_speed_l_s", "foreline_outgas_torr_l_s",
    "vent_conductance_l_s", "vent_cross_conductance_l_s", "atmosphere_torr", "burst_tau_s",
    "beam_fraction", "extraction_v_sat_v", "source_leak_ohm",
    "plate_tau_s", "back_plate_k_per_w", "back_plate_base_c", "feedthrough_k_per_w",
    "feedthrough_base_c", "transformer_tau_s", "transformer_rise_k", "transformer1_rated_w",
    "transformer2_rated_w", "transformer1_base_c", "transformer2_base_c",
    "water_tau_s", "water_flow_l_min", "water_heat_fraction", "water_cp_j_per_kg_k",
    "water_base_c",
)


def relax(x, target, tau, dt):
    """First-order lag, exact for a constant target: x moves to target with time constant tau."""
    if tau <= 0:
        return target
    return target + (x - target) * math.exp(-dt / tau)


def balance(p, inflow, outflow_speed, volume, dt):
    """Gas balance of one volume, V dp/dt = inflow - S p, exact for constant inflow and S.
    inflow in torr l/s, S in l/s, V in l."""
    if outflow_speed <= 0:
        return p + inflow * dt / volume
    return relax(p, inflow / outflow_speed, volume / outflow_speed, dt)


def smooth_min(a, b, n):
    """About min(a, b), smooth: (a^-n + b^-n)^(-1/n). Zero if either is zero."""
    if a <= 0 or b <= 0:
        return 0.0
    return (a ** -n + b ** -n) ** (-1.0 / n)


def operating_point(vset, iset, on, load):
    """A supply with voltage set point vset and current limit iset on a load whose current
    load(V) rises with V (load(0) = 0). Returns (V, I): constant voltage if load(vset) <= iset,
    else constant current, V such that load(V) = iset (bisection)."""
    if not on or vset <= 0:
        return 0.0, 0.0
    i = load(vset)
    if i <= iset:
        return vset, i
    lo, hi = 0.0, vset
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if load(mid) > iset:
            hi = mid
        else:
            lo = mid
    return lo, load(lo)


def bisect(f, lo, hi, n=80):
    """x in [lo, hi] with f(x) = 0, f rising."""
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class PlantModel:
    def __init__(self, params):
        self.p = dict(params)
        self.derived = self._calibrate()

    def _calibrate(self):
        """Fix the unknowns of the model from the owner's working point (see README.md)."""
        p = self.p
        d = {}
        # filament: hot resistance from 8 V / 90 A; the power holds it at T_hot by radiation
        d["filament_r_hot_ohm"] = p["wp_filament_voltage_v"] / p["wp_filament_current_a"]
        d["filament_power_w"] = p["wp_filament_voltage_v"] * p["wp_filament_current_a"]
        # the plasma could carry plasma_margin times the working current: the working point is
        # emission limited, and the emission it needs follows from the smooth minimum
        n = p["discharge_smooth_n"]
        i_dis = p["wp_discharge_current_a"]
        d["plasma_limit_a"] = p["plasma_margin"] * i_dis
        d["emission_a"] = (i_dis ** -n - d["plasma_limit_a"] ** -n) ** (-1.0 / n)
        t0 = p["room_temperature_k"]

        def area_cm2(t):     # radiating (and emitting) area that P_wp holds at temperature t
            return d["filament_power_w"] / (p["filament_emissivity"] * SIGMA_SB * (t ** 4 - t0 ** 4)) * 1e4

        d["filament_t_hot_k"] = bisect(lambda t: self._richardson(t) * area_cm2(t) - d["emission_a"],
                                       1000.0, 4000.0)
        d["filament_area_cm2"] = area_cm2(d["filament_t_hot_k"])
        # pumping: the speed of the turbopump comes from its data sheet (N2) and the H2/N2
        # ratio; the outgassing gives today's base reading with the pump at speed (the ion gauge
        # is calibrated for N2 and reads hydrogen low by aim_h2_factor)
        q = p["wp_gas_sccm"] * p["sccm_to_torr_l_s"]
        d["turbo_speed_l_s"] = p["turbo_speed_n2_l_s"] * p["turbo_h2_n2_ratio"]
        d["cross_base_torr"] = p["cross_base_reading_torr"] / p["aim_h2_factor"]
        d["outgassing_torr_l_s"] = d["cross_base_torr"] * self.turbo_pumping(1.0, d["cross_base_torr"], d)
        # PREDICTED pressure at the working point: S(p) p = Q0 + Q
        d["cross_wp_torr"] = bisect(
            lambda x: self.turbo_pumping(1.0, x, d) * x - d["outgassing_torr_l_s"] - q, 0.0, 1.0)
        d["aim_wp_reading_torr"] = p["aim_h2_factor"] * d["cross_wp_torr"]
        # the plasma limit at the working point voltage and chamber pressure
        d["chamber_wp_torr"] = d["cross_wp_torr"] + q / p["aperture_conductance_l_s"]
        shape = self._plasma_shape(p["wp_discharge_voltage_v"], d["chamber_wp_torr"])
        if shape <= 0:
            raise ValueError("no discharge at the working point: check discharge_v_min_v and discharge_p_min_torr")
        d["discharge_k_a_per_v15"] = d["plasma_limit_a"] / shape
        # filament: R = r_cold (T / T_room)^exponent through R_hot at T_hot
        d["filament_r_cold_ohm"] = d["filament_r_hot_ohm"] * (
            t0 / d["filament_t_hot_k"]) ** p["filament_r_exponent"]
        d["k_rad_w_per_k4"] = p["filament_emissivity"] * SIGMA_SB * d["filament_area_cm2"] * 1e-4
        # roughing pump ultimate, so that the foreline sits at its base pressure at base load
        q_base = d["outgassing_torr_l_s"] + p["foreline_outgas_torr_l_s"]
        d["rough_ultimate_torr"] = max(0.0, p["foreline_base_torr"] - q_base / p["rough_speed_l_s"])
        # plausibility only: a tungsten wire with that resistance and area (rho ~ T^exponent)
        rho = 5.5e-8 * (d["filament_t_hot_k"] / 293.0) ** p["filament_r_exponent"]
        a_m2 = d["filament_area_cm2"] * 1e-4
        diam = (4 * rho * a_m2 / (math.pi ** 2 * d["filament_r_hot_ohm"])) ** (1.0 / 3.0)
        d["wire_diameter_mm"] = diam * 1e3
        d["wire_length_cm"] = a_m2 / (math.pi * diam) * 100
        return d

    # --- single relations (used by step, and by the tests one by one) ------------------------

    def _richardson(self, t):
        p = self.p
        return p["richardson_a_per_cm2_k2"] * t * t * math.exp(-p["work_function_ev"] / (K_BOLTZMANN_EV * t))

    def _plasma_shape(self, v, p_chamber):
        p = self.p
        if v <= p["discharge_v_min_v"] or p_chamber <= p["discharge_p_min_torr"]:
            return 0.0
        dp = p_chamber - p["discharge_p_min_torr"]
        return (v - p["discharge_v_min_v"]) ** p["discharge_exponent"] * dp / (dp + p["discharge_p_half_torr"])

    def filament_resistance(self, t):
        return self.derived["filament_r_cold_ohm"] * (t / self.p["room_temperature_k"]) ** self.p["filament_r_exponent"]

    def filament_equilibrium(self, power):
        """Temperature at which radiation carries away `power` (Stefan-Boltzmann)."""
        t0 = self.p["room_temperature_k"]
        return (max(0.0, power) / self.derived["k_rad_w_per_k4"] + t0 ** 4) ** 0.25

    def emission(self, t, factor=1.0):
        """Richardson-Dushman: A_G T^2 exp(-W / kT) times the area, A."""
        return max(0.0, factor) * self._richardson(t) * self.derived["filament_area_cm2"]

    def plasma_limit(self, v, p_chamber):
        """Current the discharge can carry at voltage v and chamber pressure p, A."""
        return self.derived["discharge_k_a_per_v15"] * self._plasma_shape(v, p_chamber)

    def discharge_current(self, v, emission, p_chamber):
        return smooth_min(emission, self.plasma_limit(v, p_chamber), self.p["discharge_smooth_n"])

    def beam_current(self, v_extraction, discharge, on):
        if not on or v_extraction <= 0:
            return 0.0
        p = self.p
        return p["beam_fraction"] * discharge * (1.0 - math.exp(-v_extraction / p["extraction_v_sat_v"]))

    def turbo_pumping(self, speed_fraction, pressure, derived=None):
        """Pumping speed of the turbopump on the cross, l/s: much less when not at speed, falls
        off at high inlet pressure."""
        p = self.p
        d = derived or self.derived
        x = min(1.0, max(0.0, speed_fraction))
        f = p["turbo_stopped_fraction"] + (1.0 - p["turbo_stopped_fraction"]) * x
        return d["turbo_speed_l_s"] * f / (1.0 + max(0.0, pressure) / p["turbo_p_limit_torr"])

    def gauges(self, p_cross):
        """(AIM reading, APG reading), torr. The AIM (an ion gauge) is calibrated for N2 and reads
        hydrogen low; the APG (Pirani type) reports nothing below its floor and above its top
        (seen on the lab's TIC: 1.0000e-02 Pa and 1.0000e+05 Pa)."""
        p = self.p
        aim = p["aim_h2_factor"] * p_cross
        apg = min(p["apg_ceiling_torr"], max(p["apg_floor_torr"], p_cross))
        return aim, apg

    # --- the state ---------------------------------------------------------------------------

    def initial_state(self):
        """A cold source at base pressure, pump at speed."""
        p, d = self.p, self.derived
        state = {
            "filament_temperature": p["room_temperature_k"],
            "chamber_pressure": d["cross_base_torr"],
            "cross_pressure": d["cross_base_torr"],
            "foreline_pressure": p["foreline_base_torr"],
            "plate_power": 0.0,         # filament + discharge power, lagged by plate_tau_s, W
            "feedthrough_power": 0.0,   # filament power, lagged by plate_tau_s, W
            "transformer1_load": 0.0,   # (TDK output / rating)^2, lagged by transformer_tau_s
            "transformer2_load": 0.0,   # (REK output / rating)^2, lagged by transformer_tau_s
            "water_power": 0.0,         # filament + discharge power, lagged by water_tau_s, W
        }
        state.update(DISTURBANCES)
        return state

    def step(self, state, inputs, dt):
        """(state, inputs, dt) -> (new state, outputs). Pure: `state` is not modified."""
        p, d = self.p, self.derived
        u = dict(idle_inputs(), **inputs)
        on = lambda k: u[k] >= 0.5   # noqa: E731
        s = dict(state)

        # disturbances
        s["emission_factor"] = max(0.0, s["emission_factor"] * (1.0 + s["emission_drift_per_min"] * dt / 60.0))
        s["pressure_burst_sccm"] = relax(s["pressure_burst_sccm"], 0.0, p["burst_tau_s"], dt)

        # 1. filament: I^2 R(T) heats it, T follows the radiation equilibrium with a lag
        i_fil = max(0.0, u["filament_current"])
        p_fil = i_fil * i_fil * self.filament_resistance(s["filament_temperature"])
        s["filament_temperature"] = relax(s["filament_temperature"], self.filament_equilibrium(p_fil),
                                          p["filament_tau_s"], dt)
        t_fil = s["filament_temperature"]
        r_fil = self.filament_resistance(t_fil)
        emission = self.emission(t_fil, s["emission_factor"])

        # 3. gas and vacuum (before the discharge, which needs the chamber pressure)
        q_sccm = (max(0.0, u["gas_flow"]) if on("shutoff_open") else 0.0) + s["pressure_burst_sccm"]
        q = q_sccm * p["sccm_to_torr_l_s"]
        c_ap, atm = p["aperture_conductance_l_s"], p["atmosphere_torr"]
        p_cross0, p_fl0 = s["cross_pressure"], s["foreline_pressure"]
        s_turbo = self.turbo_pumping(u["turbo_speed"], p_cross0)
        # plasma chamber: gas in, out through the extraction aperture into the cross
        s["chamber_pressure"] = balance(s["chamber_pressure"], q + c_ap * p_cross0, c_ap,
                                        p["chamber_volume_l"], dt)
        # cross: the gas, outgassing, a little vent gas back through the turbopump; pumped by it
        c_vx = p["vent_cross_conductance_l_s"]
        s["cross_pressure"] = balance(p_cross0, q + d["outgassing_torr_l_s"] + c_vx * p_fl0,
                                      s_turbo + c_vx, p["cross_volume_l"], dt)
        # foreline (turbopump outlet and vent port): what the turbopump pumps, vent gas, emptied
        # by the roughing pump when the foreline valve is open
        c_v = p["vent_conductance_l_s"] if on("vent_open") else 0.0
        s_r = p["rough_speed_l_s"] if on("foreline_open") else 0.0
        q_fl = s_turbo * p_cross0 + p["foreline_outgas_torr_l_s"] + c_v * atm + s_r * d["rough_ultimate_torr"]
        s["foreline_pressure"] = min(atm, balance(p_fl0, q_fl, s_r + c_v, p["foreline_volume_l"], dt))
        aim, apg = self.gauges(s["cross_pressure"])

        # 2. discharge: the REK and the discharge, with the supply's own current limit
        p_ch = s["chamber_pressure"]
        rek_load = lambda v: self.discharge_current(v, emission, p_ch) + v / p["rek_bleed_ohm"]  # noqa: E731
        v_dis, i_rek = operating_point(u["rek_vset"], u["rek_iset"], on("rek_on"), rek_load)
        i_dis = self.discharge_current(v_dis, emission, p_ch)
        r_rek = v_dis / i_rek if i_rek > 0 else p["rek_bleed_ohm"]

        # 4. extraction: beam current, the source supply with its leakage and current limit
        both = on("source_on") and on("puller_on")
        v_p = max(0.0, u["puller_voltage"]) if on("puller_on") else 0.0
        src_load = lambda v: self.beam_current(v + v_p, i_dis, both) + v / p["source_leak_ohm"]  # noqa: E731
        v_src, i_src = operating_point(u["source_vset"], u["source_iset"], on("source_on"), src_load)
        i_beam = self.beam_current(v_src + v_p, i_dis, both and v_src > 0)
        r_src = v_src / i_src if i_src > 0 else p["source_leak_ohm"]
        i_cup = i_beam if on("cup_in") else 0.0

        # 5. heat on the platform and in the water
        p_dis = v_dis * i_dis
        p_rek = v_dis * i_rek            # what the REK delivers (discharge and bleeder)
        heat = p_fil + p_dis
        s["plate_power"] = relax(s["plate_power"], heat, p["plate_tau_s"], dt)
        s["feedthrough_power"] = relax(s["feedthrough_power"], p_fil, p["plate_tau_s"], dt)
        s["transformer1_load"] = relax(s["transformer1_load"], (p_fil / p["transformer1_rated_w"]) ** 2,
                                       p["transformer_tau_s"], dt)
        s["transformer2_load"] = relax(s["transformer2_load"], (p_rek / p["transformer2_rated_w"]) ** 2,
                                       p["transformer_tau_s"], dt)
        s["water_power"] = relax(s["water_power"], heat, p["water_tau_s"], dt)
        water_k_per_w = p["water_heat_fraction"] / (p["water_flow_l_min"] / 60.0 * p["water_cp_j_per_kg_k"])
        water = {k: base + water_k_per_w * s["water_power"] for k, base in p["water_base_c"].items()}

        out = {
            "filament_temperature": t_fil, "filament_resistance": r_fil, "filament_power": p_fil,
            "filament_voltage": i_fil * r_fil, "emission": emission,
            "discharge_voltage": v_dis, "discharge_current": i_dis, "rek_current": i_rek,
            "rek_load": r_rek, "discharge_power": p_dis,
            "gas_into_source": q_sccm, "pumping_speed": s_turbo,
            "chamber_pressure": s["chamber_pressure"], "cross_pressure": s["cross_pressure"],
            "foreline_pressure": s["foreline_pressure"], "aim_reading": aim, "apg_reading": apg,
            "source_voltage": v_src, "source_current": i_src, "source_load": r_src,
            "beam_current": i_beam, "cup_current": i_cup, "heat_power": heat,
            "back_plate_temperature": p["back_plate_base_c"] + p["back_plate_k_per_w"] * s["plate_power"],
            "feedthrough_temperature": p["feedthrough_base_c"] + p["feedthrough_k_per_w"] * s["feedthrough_power"],
            "transformer1_temperature": p["transformer1_base_c"] + p["transformer_rise_k"] * s["transformer1_load"],
            "transformer2_temperature": p["transformer2_base_c"] + p["transformer_rise_k"] * s["transformer2_load"],
            "water_temperatures": water,
        }
        return s, out

    def settle(self, state, inputs, seconds, dt=0.01):
        """Run with constant inputs. Returns (state, outputs) at the end."""
        out = None
        for _ in range(max(1, int(round(seconds / dt)))):
            state, out = self.step(state, inputs, dt)
        return state, out
