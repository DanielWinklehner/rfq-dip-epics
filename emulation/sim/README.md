# mist2sim: device simulators

Every serial or TCP device of MIST-2 replaced by a program that speaks its real wire protocol
over TCP. One simulator = one TCP port = one serial line or bus. Python 3.10+, standard library
and PyYAML. Acceptance test: `emulation/sim/run_tests.sh`.

## Start one and talk to it

```
cd emulation/sim
python3 -m mist2sim --config examples/valvebox.yaml     # logs to stdout, stops on Ctrl-C / SIGTERM
printf 'I\nA\nSs11\ngs1\n' | nc -q1 localhost 5012     # device port
echo '{"cmd": "info"}' | nc -q1 localhost 6012         # control port = device port + 1000
```

Each reply is held back by the time its characters need on the real line,
`(request + reply bytes, terminators included) x bits_per_char / baud + turnaround_ms`, counted
from the arrival of the request. Requests are served one at a time in order of arrival; one that
gets no reply still occupies the line for its own length. A new connection replaces the old one.

## Configuration: a YAML list of simulators

| Key | Meaning |
|---|---|
| `name`, `type`, `port` | required. `type` is a registered type (`libcom1`, ...) |
| `control_port` | default `port + 1000` |
| `baud`, `bits_per_char`, `turnaround_ms` | line timing; defaults 9600, 10, 0 (a type can change the defaults) |
| `in_terminator`, `out_terminator` | any string, e.g. `"\r"`, `"\r\n"`, `";FF"`; default `"\n"` |
| `options` | belongs to the type, see the type's `OPTIONS` |

Unknown keys and options are errors. **libcom1** options: `identity`, `firmware`,
`number_format` (`avr` = dtostre, `g` = `%g` as on the Opta), `out_buffer` (160), `in_buffer`
(128), `comm_timeout_ms` (0 = off), `on_timeout` (`{channel: value}`), `channels` in query-all
order: `{id: s1, access: r|w|rw, behaviour: ...}`. Each channel is a signal of the same name.
Behaviours: `constant` (`value`), `analog` (`value, noise, tau, lo, hi, step`), `readback`
(reads what was written; `value, tau, lo, hi, step`), `relay` (reads 1 if exactly 1 was written,
else 0; `value`). Writes to `constant` and `analog` are accepted and ignored. libcom1 defaults:
115200 baud, in `"\n"`, out `"\r\n"` (`Serial.println`; use `"\n"` for an Opta over TCP).
Examples: `examples/valvebox.yaml`, `examples/thermocouple.yaml`.

## Control protocol: one JSON object per line, one reply per line

Every reply has `"ok": true`, or `"ok": false` and `"error"`. `unit` is optional everywhere
(default: the whole simulator). `mist2sim.control.ControlClient(host, port)` has one method per
command (`info()`, `fault(mode, unit, duration, ms)`, `clear(mode, unit)`, `get(signal)`,
`set(signal, value)`, `release(signal)`, `stats(reset)`) and `call(dict)` for raw requests.

```
{"cmd": "info"}                                   name, type, port, units, signals, settings, options
{"cmd": "fault", "mode": "silent", "unit": 2, "duration": 5}   takes input, never answers (5 s)
{"cmd": "fault", "mode": "close"}                 drops the client, refuses new ones while active
{"cmd": "fault", "mode": "garbage"}               replies corrupted, same length, correctly timed
{"cmd": "fault", "mode": "trip"}                  device specific (error if the type has none)
{"cmd": "fault", "mode": "slow", "ms": 200}       extra reply delay
{"cmd": "clear"}           {"cmd": "clear", "mode": "silent", "unit": 2}
{"cmd": "get"}             all signals {value, target, external} and the active faults
{"cmd": "get", "signal": "s1"}
{"cmd": "set", "signal": "pressure", "value": 1e-6}   held under outside control ...
{"cmd": "release", "signal": "pressure"}               ... until released
{"cmd": "stats", "reset": true}   requests, replies, bytes_in/out, busy_s, per_unit, elapsed_s
```

A silenced unit does not execute what it is sent. `get` returns true values (no noise). `stats`
counts since start or since the last `reset`; `busy_s` includes turnaround and `slow`.

## Writing a device module

Put one file in `mist2sim/devices/`. It is imported automatically; `@register("type")` makes it
usable as `type:` in a configuration. Nothing else needs editing. The base class does TCP,
framing, timing, faults, statistics and the control port. You write `setup()` and `handle()`.

* `handle(request, unit)`: `request` is bytes without the input terminator. Return `None` (no
  reply), a line, or a list of lines (bytes or str, without terminator).
* `self.add_signal(name, value, tau=, noise=, lo=, hi=, step=)`: a `Signal`. Device code writes
  `sig.target`, reads `sig.read()` (with noise) or `sig.value` (true value). Everything the plant
  model should see or drive must be a signal.
* `self.options`, `self.settings`, `self.log`, `self.now()` (seconds, from the injectable clock).
* Optional: `trip(unit)` and `trip_cleared(unit)`; `self.faulted(mode, unit)`; `tick(now)` for
  periodic work, returns the next time it wants to run (or `None`) and may call `self.send(line)`
  for unsolicited output; `self.add_coupling(fn)` with `fn(dt, signals)`, stepped before every
  request, tick and control command (example: a relay ramps a speed, the speed sets a status).
* A bus: `self.add_unit(address)` in `setup()` and `route(request)` returning a unit address,
  `ALL` (broadcast: `handle` is called for every unit) or `None`. Unknown addresses get no answer.

Minimal single-unit device:

```python
from mist2sim.core import Simulator, register

@register("demo_psu")
class DemoPSU(Simulator):
    """'V?' -> 'V=12.000', 'V 12' sets (no reply), 'OUT 1' / 'OUT 0' -> 'OK'."""
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r"}
    OPTIONS = {"vmax": 30.0}

    def setup(self):
        self.volts = self.add_signal("volts", 0.0, tau=0.5, noise=0.002, lo=0, hi=self.options["vmax"])
        self.output = self.add_signal("output", 0.0)

    def handle(self, request, unit):
        cmd = request.decode("ascii", "replace").strip()
        if cmd == "V?":
            return "V=%.3f" % (self.volts.read() if self.output.value else 0.0)
        if cmd.startswith("V "):
            try:
                self.volts.target = float(cmd[2:])
            except ValueError:
                return "ERR"
            return None
        if cmd in ("OUT 0", "OUT 1"):
            self.output.target = float(cmd[-1])
            return "OK"
        return "ERR"

    def trip(self, unit):
        self.output.target = 0.0            # fault "trip": the output switches off
```

Minimal multi-unit bus:

```python
from mist2sim.core import ALL, Simulator, register

@register("demo_bus")
class DemoBus(Simulator):
    """'#<n> T?' -> '#<n> T=<temp>'; '#AL RST' resets every unit and nobody answers."""
    OPTIONS = {"units": [1, 2]}

    def setup(self):
        for u in self.options["units"]:
            self.add_unit(u)
            self.add_signal("%d.temp" % u, 20.0 + u, noise=0.05)

    def route(self, request):
        head = request.split(b" ", 1)[0]
        if head == b"#AL":
            return ALL
        if head[:1] == b"#" and head[1:].isdigit():
            return int(head[1:])
        return None                         # not addressed: nobody answers

    def handle(self, request, unit):
        temp = self.signals["%d.temp" % unit]
        if request.endswith(b" RST"):
            temp.target = 20.0
            return None
        if request.endswith(b" T?") and not request.startswith(b"#AL"):
            return "#%d T=%.2f" % (unit, temp.read())
        return None
```

Test it without sockets, with a fake clock, through `process()`; or with real sockets in a
background thread:

```python
from mist2sim.core import FakeClock, SimThread, build
sim = build({"name": "psu", "type": "demo_psu", "port": 0}, clock=FakeClock())
assert sim.process(b"OUT 1") == [b"OK"]
with SimThread([sim]):          # port 0: sim.port and sim.control_port are picked by the OS
    pass                        # connect to ("127.0.0.1", sim.port), ControlClient(..., sim.control_port)
```

These three examples are run by `tests/test_readme.py`.

## Plant model

Without it every simulator is an island (a fixed load, constant pressures). The plant model
connects them: one more client of the control ports, in its own process. It reads the
actuators, steps a small model of the source and writes the process values back (`set`), ten
times per second. It changes no simulator. Stop it and every device has its own behaviour again.

```
python3 -m mist2sim.plant --config config/plant.yaml     # in emulation/sim
make -C emulation up-plant       # the emulation with the plant (container plant, 172.30.0.30)
make -C emulation plant-stop     # stop only the plant: every device goes back to its own model
make -C emulation plant-logs     # its log: one status line every 10 s, events, never > 1 line/s
make -C emulation down-plant     # everything down, the plant included
```

Code: `mist2sim/plant/model.py` is a pure step function `(state, inputs, dt) -> (state,
outputs)`, no sockets, no clock (usable in a notebook: `PlantModel(load_params(path))`,
`model.step(...)`, `model.settle(...)`). `mist2sim/plant/process.py` talks to the simulators.
Configuration `config/plant.yaml`: control ports of the simulators (`links`), which signal feeds
which model input (`inputs`), which signal each output drives (`outputs`), and the model
parameters (`model`, each with value, unit and source). A simulator that is not there or goes
away is tried again every `retry_s`; the model keeps running on its last known values and the
status line names it. On SIGTERM or SIGINT the plant releases every signal it has taken.
Loop design numbers: `python3 tools/plant_step_response.py` (gain, dead time, time constant at
three working points; properties of the model, not of MIST-2).

### Signals

| Reads (model input) | Drives (model output) |
|---|---|
| `tdk.mc` filament current | `tdk.load_ohm` filament resistance R(T) |
| `rek.1.vset`, `rek.1.iset`, `rek.1.output` | `rek.1.load_ohm` = V / I of the discharge operating point |
| `mfc.254.flow` (% of 50 sccm) | `aim.pressure` source vessel (torr) |
| `valvebox.s1` foreline, `s2` MFC shutoff, `s3` vent, `s4` Faraday cup | `gauges.p2` diagnostic box, `gauges.p1` foreline (torr) |
| `nt20_1.speed` (source), `nt20_2.speed` (diagnostic box), / 1200 Hz | `faradaycup.c1` cup current (A) |
| `mat_opt.1.vset`, `.iset`, `.output` (ion source supply) | `mat_opt.1.load_ohm` = V / I of the source supply |
| `mat_opt.2.vout`, `.output` (puller supply) | `thermocouple.t1`..`t4`, `sensorbox.t1`..`t7` (degC) |

Model inputs, in this order in `config/plant.yaml`: `filament_current`, `rek_vset`, `rek_iset`, `rek_on`, `gas_flow`, `shutoff_open`, `foreline_open`, `vent_open`, `cup_in`, `turbo1_speed`, `turbo2_speed`, `source_vset`, `source_iset`, `source_on`, `puller_voltage`, `puller_on`.
A missing one is 0 (off, closed, stopped).

### Equations (model.py, in this order every step)

```
Filament     P_f   = I_f^2 R(T)                    R(T) = R_hot (T / T_hot)^r_exp
             T_eq  = (P_f / (eps sigma A) + T_room^4)^(1/4)        Stefan-Boltzmann
             dT/dt = (T_eq - T) / filament_tau                     (thermal lag)
             I_e   = emission_factor  A_G T^2 exp(-W / kT)  A      Richardson-Dushman
Gas          Q     = gas_flow (only with the shutoff valve open) + burst        [sccm]
             V_ch dp_ch/dt  = Q - C_ap (p_ch - p_src)                         plasma chamber
             V_src dp_src/dt = Q + Q0_src + C_vent (p_atm - p_src) - S1 p_src - C_beam (p_src - p_diag)
             V_diag dp_diag/dt = Q0_diag + C_beam (p_src - p_diag) - S2 p_diag
             V_fl dp_fl/dt  = S1 p_src + S2 p_diag + Q_fl - S_rough (p_fl - p_ult)   S_rough = 0 with the foreline valve closed
             S_i   = S_turbo (f_stop + (1 - f_stop) speed_i / rated) / (1 + p / p_lim)
             Q0_*, p_ult: chosen so that the pumped, gas-free plant reads today's constants
Discharge    I_plasma(V) = k (V - V_min)^1.5 (p_ch - p_min) / (p_ch - p_min + p_half)   0 below V_min or p_min
             I_dis(V)    = (I_e^-n + I_plasma^-n)^(-1/n)            emission limit, smooth min, plasma limit
             REK on the load I_dis(V) + V / R_bleed: CV at vset if that draws <= iset, else CC at the V
             where it draws iset. The plant writes R = V / I: the REK simulator's own CV/CC logic
             then lands on that point, and its current limit keeps working.
Extraction   I_beam = beam_fraction I_dis (1 - exp(-(V_src + V_puller) / V_sat))  only with both on
             source supply on the load I_beam(V) + V / R_leak, same CV/CC rule; R = V / I written
             cup current = I_beam with the cup in (valve s4), else 0
Heat         P_h = P_f + V_dis I_dis
             thermocouple_i = base_i + tc_gain P_h lagged by tc_tau
             water_i        = base_i + water_fraction P_h / (rho c_p flow) lagged by water_tau
```

All lags are integrated exactly for a constant input over one step, so any `dt` is stable. The
time constants of the heat are minutes on a real source; the defaults (20 s and 40 s) are
chosen so that a desk session sees an effect within a minute. Change them in `config/plant.yaml`.

### Disturbances: the plant's control port (6090, JSON lines as on a simulator)

```
{"cmd": "get"}                                     model state, inputs, links
{"cmd": "get", "signal": "filament_temperature"}   one value (also emission, discharge_current,
                                                   source_pressure, beam_current, ...)
{"cmd": "set", "signal": "emission_factor", "value": 0.8}          emission -20 % at once
{"cmd": "set", "signal": "emission_drift_per_min", "value": -0.05} emission falls 5 %/min
{"cmd": "set", "signal": "pressure_burst_sccm", "value": 20}       extra gas, decays (burst_tau_s)
{"cmd": "release", "signal": "emission_factor"}                    back to neutral
```

`ControlClient("172.30.0.30", 6090)` works as on a simulator (`get`, `set`, `release`, `info`).

### Not modelled

Space charge and plasma physics beyond the two limits; the arc and filament burn-out at high
pressure; the cusp magnets; filament evaporation and ageing (only as `emission_drift_per_min`);
gas consumption by the discharge; outgassing that rises with temperature; turbopump stall from
a high foreline pressure; viscous flow while venting; the roughing pump (always running); the
cooling water flows (the sensor box flows are not read); the lens supplies and puller current;
beam transport (every extracted ion reaches the cup); the MFC seeing its shutoff valve closed (it
reports its own flow); the cold-junction channels j1..j4 of the thermocouple board; gauge
heads switched off (the nAIM simulator still decides what it reports when off).

### Parameters (config/plant.yaml, section model)

| Parameter | Default | Unit | Source |
|---|---|---|---|
| `filament_tau_s` | 1 | s | free choice: 'about a second, which matches a thermal filament' (plan/controls.yaml, software.loops) |
| `filament_r_hot_ohm` | 0.025 | ohm | estimate: the hot filament assumed by the TDK simulator (hv.yaml load_ohm) |
| `filament_t_hot_k` | 2600 | K | estimate: a usual temperature of an emitting tungsten filament |
| `filament_r_exponent` | 1.2 | 1 | law (fit): tungsten resistivity rises about as T^1.2 between 300 and 3000 K |
| `filament_area_cm2` | 13 | cm2 | estimate: chosen so that about 1 kW (200 A) holds the filament at about 2600 K; also the emitting area |
| `filament_emissivity` | 0.3 | 1 | law (tabulated): total emissivity of tungsten near 2600 K |
| `room_temperature_k` | 293 | K | free choice |
| `richardson_a_per_cm2_k2` | 60 | A/(cm2 K2) | law (tabulated): Richardson constant of tungsten |
| `work_function_ev` | 4.54 | eV | law (tabulated): work function of tungsten |
| `discharge_v_min_v` | 25 | V | estimate: no discharge below this voltage (H2 ionisation 15.4 V plus margin) |
| `discharge_k_a_per_v15` | 0.04 | A/V^1.5 | estimate: the plasma carries about 20 A at 100 V and 5 sccm, near the REK rating (24 A) |
| `discharge_exponent` | 1.5 | 1 | law (shape only): space-charge limited current rises as V^1.5 (Child-Langmuir) |
| `discharge_p_min_torr` | 0.0005 | torr | estimate: no discharge below this plasma chamber pressure |
| `discharge_p_half_torr` | 0.002 | torr | estimate: the plasma limit is half its maximum at p_min + p_half |
| `discharge_smooth_n` | 3 | 1 | free choice: sharpness of the transition from emission limit to plasma limit |
| `rek_bleed_ohm` | 10000 | ohm | free choice: a bleeder across the REK output, so that its current limit always has a load to act on |
| `sccm_to_torr_l_s` | 0.01267 | torr l/s per sccm | law: definition of the sccm (760 torr, 0 degC) |
| `aperture_conductance_l_s` | 8 | l/s | estimate: molecular flow of H2 through an extraction aperture of about 5 mm |
| `chamber_volume_l` | 2 | l | estimate: plasma chamber |
| `source_volume_l` | 50 | l | estimate: source vacuum vessel |
| `diag_volume_l` | 30 | l | estimate: diagnostic box |
| `beamline_conductance_l_s` | 5 | l/s | estimate: between source vessel and diagnostic box |
| `turbo_speed_l_s` | 200 | l/s | estimate: H2 pumping speed of each turbopump at rated speed (the pump models are not known) |
| `turbo_stopped_fraction` | 0.01 | 1 | estimate: what a stopped turbopump still pumps (through to the foreline) |
| `turbo_p_limit_torr` | 0.01 | torr | estimate: inlet pressure at which a turbopump has lost half its speed |
| `source_base_torr` | 2e-06 | torr | free choice: the constant of the aim simulator today (rack.yaml), base pressure with pumps at speed |
| `diag_base_torr` | 8e-07 | torr | free choice: the constant of gauges p2 today (rack.yaml) |
| `foreline_base_torr` | 0.03 | torr | free choice: the constant of gauges p1 today (rack.yaml) |
| `foreline_volume_l` | 2 | l | estimate: foreline between turbopumps and foreline valve (the gauge is assumed there) |
| `rough_speed_l_s` | 5 | l/s | estimate: roughing pump (make and model not known) |
| `foreline_outgas_torr_l_s` | 0.001 | torr l/s | estimate: outgassing of the foreline |
| `vent_conductance_l_s` | 10 | l/s | estimate: vent valve into the source vessel |
| `atmosphere_torr` | 760 | torr | law |
| `burst_tau_s` | 2 | s | free choice: decay of a pressure burst set through the plant's control port |
| `beam_fraction` | 0.0002 | A/A | estimate: extracted beam current per A of discharge current at saturation (10 A -> 2 mA, within the 15 mA source supply) |
| `extraction_v_sat_v` | 8000 | V | estimate: the beam current rises as 1 - exp(-V / v_sat) with the extraction voltage (source + puller) |
| `source_leak_ohm` | 2e+08 | ohm | free choice: leakage of the source supply output, 100 uA at 20 kV |
| `tc_tau_s` | 20 | s | free choice: minutes in reality, short so that a desk session sees an effect within a minute |
| `tc_gain_k_per_w` | 0.01 | K/W | estimate: 3 kW of filament and discharge power heat the source plates by 30 K |
| `tc_base_c` | t1 35, t2 41, t3 38, t4 33 | degC | free choice: the constants of the thermocouple simulator today (hv.yaml) |
| `water_tau_s` | 40 | s | free choice: minutes in reality, short so that a desk session sees an effect within a minute |
| `water_flow_l_min` | 1 | l/min | estimate: within 0.25 to 2 l/min per branch (plan/controls.yaml) |
| `water_heat_fraction` | 0.3 | 1 | estimate: share of the heat power each sensor box channel sees (which sensor sits where is not known) |
| `water_cp_j_per_kg_k` | 4186 | J/(kg K) at 1 kg/l | law: heat capacity of water |
| `water_base_c` | t1 24, t2 25, t3 26, t4 27, t5 28, t6 29, t7 30 | degC | free choice: the constants of the sensor box simulator today (rack.yaml) |
