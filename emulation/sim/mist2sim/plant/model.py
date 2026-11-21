"""The MIST-2 plant model: a pure, deterministic step function, no I/O, no clock.

    from mist2sim.plant.model import PlantModel, load_params, idle_inputs
    m = PlantModel(load_params("config/plant.yaml"))
    state = m.initial_state()
    state, out = m.step(state, dict(idle_inputs(), filament_current=200.0), 0.1)

`step` never changes the state it is given; it returns a new one. Every number comes from the
parameters (config/plant.yaml, section `model`). The equations are listed in README.md,
section "Plant model". Units: SI except pressures (torr, as the gauges), flows (sccm) and
temperatures of the sensors (deg C).
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
    "vent_open": "0/1, vent valve",
    "cup_in": "0/1, Faraday cup moved in",
    "turbo1_speed": "fraction of the rated speed, turbopump of the source",
    "turbo2_speed": "fraction of the rated speed, turbopump of the diagnostic box",
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
    "pressure_burst_sccm": 0.0,      # extra gas into the plasma chamber, decays with burst_tau_s
}


def idle_inputs():
    """Everything off, valves closed, pumps stopped."""
    return {k: 0.0 for k in INPUTS}


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
    "filament_tau_s", "filament_r_hot_ohm", "filament_t_hot_k", "filament_r_exponent",
    "filament_area_cm2", "filament_emissivity", "room_temperature_k",
    "richardson_a_per_cm2_k2", "work_function_ev",
    "discharge_v_min_v", "discharge_k_a_per_v15", "discharge_exponent", "discharge_p_min_torr",
    "discharge_p_half_torr", "discharge_smooth_n", "rek_bleed_ohm",
    "sccm_to_torr_l_s", "aperture_conductance_l_s", "chamber_volume_l", "source_volume_l",
    "diag_volume_l", "beamline_conductance_l_s", "turbo_speed_l_s", "turbo_stopped_fraction",
    "turbo_p_limit_torr", "source_base_torr", "diag_base_torr", "foreline_base_torr",
    "foreline_volume_l", "rough_speed_l_s", "foreline_outgas_torr_l_s", "vent_conductance_l_s",
    "atmosphere_torr", "burst_tau_s",
    "beam_fraction", "extraction_v_sat_v", "source_leak_ohm",
    "tc_tau_s", "tc_gain_k_per_w", "tc_base_c",
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


class PlantModel:
    def __init__(self, params):
        self.p = dict(params)
        p = self.p
        # Gas loads (outgassing) that give today's constant gauge readings with the pumps at speed.
        p_src, p_diag = p["source_base_torr"], p["diag_base_torr"]
        c_beam = p["beamline_conductance_l_s"]
        s1, s2 = self.turbo_speed(1.0, p_src), self.turbo_speed(1.0, p_diag)
        self.q0_source = max(0.0, p_src * (s1 + c_beam) - c_beam * p_diag)
        self.q0_diag = max(0.0, p_diag * (s2 + c_beam) - c_beam * p_src)
        q_base = self.q0_source + self.q0_diag + p["foreline_outgas_torr_l_s"]
        # ultimate pressure of the roughing pump, so that the foreline reads its base pressure
        self.p_rough = max(0.0, p["foreline_base_torr"] - q_base / p["rough_speed_l_s"])
        # filament: R = r_cold (T / T_room)^exponent, through R_hot at T_hot
        self.r_cold = p["filament_r_hot_ohm"] * (
            p["room_temperature_k"] / p["filament_t_hot_k"]) ** p["filament_r_exponent"]
        self.k_rad = p["filament_emissivity"] * SIGMA_SB * p["filament_area_cm2"] * 1e-4  # W/K^4

    # --- single relations (used by step, and by the tests one by one) ------------------------

    def filament_resistance(self, t):
        p = self.p
        return self.r_cold * (t / p["room_temperature_k"]) ** p["filament_r_exponent"]

    def filament_equilibrium(self, power):
        """Temperature at which radiation carries away `power` (Stefan-Boltzmann)."""
        t0 = self.p["room_temperature_k"]
        return (max(0.0, power) / self.k_rad + t0 ** 4) ** 0.25

    def emission(self, t, factor=1.0):
        """Richardson-Dushman: A_G T^2 exp(-W / kT) times the area, A."""
        p = self.p
        j = p["richardson_a_per_cm2_k2"] * t * t * math.exp(-p["work_function_ev"] /
                                                           (K_BOLTZMANN_EV * t))
        return max(0.0, factor) * j * p["filament_area_cm2"]

    def plasma_limit(self, v, p_chamber):
        """Current the discharge can carry at voltage v and chamber pressure p, A."""
        p = self.p
        if v <= p["discharge_v_min_v"] or p_chamber <= p["discharge_p_min_torr"]:
            return 0.0
        dp = p_chamber - p["discharge_p_min_torr"]
        gas = dp / (dp + p["discharge_p_half_torr"])
        return p["discharge_k_a_per_v15"] * (v - p["discharge_v_min_v"]) ** p["discharge_exponent"] * gas

    def discharge_current(self, v, emission, p_chamber):
        return smooth_min(emission, self.plasma_limit(v, p_chamber), self.p["discharge_smooth_n"])

    def beam_current(self, v_extraction, discharge, on):
        if not on or v_extraction <= 0:
            return 0.0
        p = self.p
        return p["beam_fraction"] * discharge * (1.0 - math.exp(-v_extraction / p["extraction_v_sat_v"]))

    def turbo_speed(self, speed_fraction, pressure):
        """Pumping speed of one turbopump, l/s: much less when not at speed, falls off at high
        inlet pressure."""
        p = self.p
        x = min(1.0, max(0.0, speed_fraction))
        f = p["turbo_stopped_fraction"] + (1.0 - p["turbo_stopped_fraction"]) * x
        return p["turbo_speed_l_s"] * f / (1.0 + max(0.0, pressure) / p["turbo_p_limit_torr"])

    # --- the state ---------------------------------------------------------------------------

    def initial_state(self):
        """A cold source at today's base pressures, pumps assumed at speed."""
        p = self.p
        state = {
            "filament_temperature": p["room_temperature_k"],
            "chamber_pressure": p["source_base_torr"],
            "source_pressure": p["source_base_torr"],
            "diag_pressure": p["diag_base_torr"],
            "foreline_pressure": p["foreline_base_torr"],
            "tc_power": 0.0,        # heat power as the source thermocouples see it (lagged), W
            "water_power": 0.0,     # heat power as the cooling water sees it (lagged), W
            "heat_power": 0.0,      # filament + discharge power of the last step, W
        }
        state.update(DISTURBANCES)
        return state

    def step(self, state, inputs, dt):
        """(state, inputs, dt) -> (new state, outputs). Pure: `state` is not modified."""
        p = self.p
        u = dict(idle_inputs(), **inputs)
        on = lambda k: u[k] >= 0.5   # noqa: E731
        s = dict(state)

        # disturbances
        s["emission_factor"] = max(0.0, s["emission_factor"] * (1.0 + s["emission_drift_per_min"] * dt / 60.0))
        s["pressure_burst_sccm"] = relax(s["pressure_burst_sccm"], 0.0, p["burst_tau_s"], dt)

        # 1. filament: I^2 R(T) heats it, T follows the radiation equilibrium with a lag
        i_fil = max(0.0, u["filament_current"])
        r_fil = self.filament_resistance(s["filament_temperature"])
        p_fil = i_fil * i_fil * r_fil
        s["filament_temperature"] = relax(s["filament_temperature"], self.filament_equilibrium(p_fil),
                                          p["filament_tau_s"], dt)
        t_fil = s["filament_temperature"]
        r_fil = self.filament_resistance(t_fil)
        emission = self.emission(t_fil, s["emission_factor"])

        # 3. gas and vacuum (before the discharge, which needs the chamber pressure)
        q_sccm = (max(0.0, u["gas_flow"]) if on("shutoff_open") else 0.0) + s["pressure_burst_sccm"]
        q = q_sccm * p["sccm_to_torr_l_s"]
        c_ap, c_beam = p["aperture_conductance_l_s"], p["beamline_conductance_l_s"]
        s1 = self.turbo_speed(u["turbo1_speed"], s["source_pressure"])
        s2 = self.turbo_speed(u["turbo2_speed"], s["diag_pressure"])
        c_vent = p["vent_conductance_l_s"] if on("vent_open") else 0.0
        atm = p["atmosphere_torr"]
        p_src0 = s["source_pressure"]
        # plasma chamber: gas in, out through the extraction aperture into the source vessel
        s["chamber_pressure"] = balance(s["chamber_pressure"], q + c_ap * p_src0, c_ap,
                                        p["chamber_volume_l"], dt)
        # source vessel: gas from the chamber, outgassing, vent; pumped by turbo 1
        s["source_pressure"] = balance(
            p_src0, q + self.q0_source + c_vent * atm + c_beam * s["diag_pressure"],
            s1 + c_vent + c_beam, p["source_volume_l"], dt)
        # diagnostic box: gas from the source vessel through the beam line, pumped by turbo 2
        s["diag_pressure"] = balance(s["diag_pressure"], self.q0_diag + c_beam * p_src0,
                                     s2 + c_beam, p["diag_volume_l"], dt)
        # foreline: what both turbos pump, emptied by the roughing pump when the valve is open
        q_fl = s1 * p_src0 + s2 * state["diag_pressure"] + p["foreline_outgas_torr_l_s"]
        s_r = p["rough_speed_l_s"] if on("foreline_open") else 0.0
        s["foreline_pressure"] = min(atm, balance(s["foreline_pressure"], q_fl + s_r * self.p_rough,
                                                  s_r, p["foreline_volume_l"], dt))

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

        # 5. heat: thermocouples and cooling water follow the power with their lags
        heat = p_fil + v_dis * i_dis
        s["heat_power"] = heat
        s["tc_power"] = relax(s["tc_power"], heat, p["tc_tau_s"], dt)
        s["water_power"] = relax(s["water_power"], heat, p["water_tau_s"], dt)
        tc = {k: base + p["tc_gain_k_per_w"] * s["tc_power"] for k, base in p["tc_base_c"].items()}
        water_k_per_w = p["water_heat_fraction"] / (p["water_flow_l_min"] / 60.0 * p["water_cp_j_per_kg_k"])
        water = {k: base + water_k_per_w * s["water_power"] for k, base in p["water_base_c"].items()}

        out = {
            "filament_temperature": t_fil, "filament_resistance": r_fil, "filament_power": p_fil,
            "emission": emission,
            "discharge_voltage": v_dis, "discharge_current": i_dis, "rek_current": i_rek,
            "rek_load": r_rek,
            "gas_into_source": q_sccm,
            "chamber_pressure": s["chamber_pressure"], "source_pressure": s["source_pressure"],
            "diag_pressure": s["diag_pressure"], "foreline_pressure": s["foreline_pressure"],
            "source_voltage": v_src, "source_current": i_src, "source_load": r_src,
            "beam_current": i_beam, "cup_current": i_cup,
            "heat_power": heat, "thermocouples": tc, "water_temperatures": water,
        }
        return s, out

    def settle(self, state, inputs, seconds, dt=0.01):
        """Run with constant inputs. Returns (state, outputs) at the end."""
        out = None
        for _ in range(max(1, int(round(seconds / dt)))):
            state, out = self.step(state, inputs, dt)
        return state, out
