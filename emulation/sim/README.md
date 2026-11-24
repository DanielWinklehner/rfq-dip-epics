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
(128), `comm_timeout_ms` (0 = off), `on_timeout` (`{channel: value}`), `protocol` (2; 1 = a board
flashed before protocol 2: `A`, `s`, `q` only, every other command answered `ERR0` and logged as
"protocol 1: ... answered ERR0", no communication timeout), `channels` in query-all
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
{"cmd": "fault", "mode": "slow_second", "unit": 1, "ms": 300}   the second reply after this comes late, once; then the fault ends
{"cmd": "clear"}           {"cmd": "clear", "mode": "silent", "unit": 2}
{"cmd": "get"}             all signals {value, target, external} and the active faults
{"cmd": "get", "signal": "s1"}
{"cmd": "set", "signal": "pressure", "value": 1e-6}   held under outside control ...
{"cmd": "release", "signal": "pressure"}               ... until released
{"cmd": "stats", "reset": true}   requests, replies, bytes_in/out, busy_s, per_unit, heads, elapsed_s
```

A silenced unit does not execute what it is sent. `get` returns true values (no noise). `stats`
counts since start or since the last `reset`; `busy_s` includes turnaround and `slow`; `heads`
counts the requests by their first character (libcom1 `S` and `s` are sets, nAIM `!` a command).

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
the working point and two points below; properties of the model, not of MIST-2).

### The machine (phase 1, owner 2026-11-21)

Ion source with a hairpin filament on the high-voltage platform, a conical high-voltage break,
then ONE chamber at ground: a CF 10" six-way cross (extraction in its upstream flange, Faraday
cup from the top). ONE turbopump (turbopump 1) on the bottom flange. The nAIM and the APG sit
side by side on a side flange, so both measure the cross. Not in phase 1, and not used by the
plant: turbopump 2 (`nt20_2` keeps running as a simulator), the second gauge channel `gauges.p2`
(an AIM for phase 2), a diagnostic box. The foreline has no gauge in the control system yet: its
pressure is a model state, `foreline_pressure` on the plant's control port. Thermocouples t1..t4:
back plate, filament feedthrough, isolation transformer 1, isolation transformer 2. The water
temperatures are computed but read by no simulator since the sensor box left the rack IOC
(T26); the flow meter Opta that replaces it measures flows only, not modelled.

### Signals

| Reads (model input) | Drives (model output) |
|---|---|
| `tdk.mc` filament current | `tdk.load_ohm` filament resistance R(T) |
| `rek.1.vset`, `rek.1.iset`, `rek.1.output` | `rek.1.load_ohm` = V / I of the discharge operating point |
| `mfc.254.flow` (% of 5 sccm H2) | `aim.pressure` nAIM reading of the cross (torr) |
| `valvebox.s1` foreline, `s2` MFC shutoff, `s3` vent (turbopump), `s4` Faraday cup | `gauges.p1` APG reading of the cross (torr) |
| `nt20_1.speed` / 600 Hz | `faradaycup.i1` cup current (A; ASSUMED: i1 of FC1 is the cup current) |
| `mat_opt.1.vset`, `.iset`, `.output` (ion source supply) | `mat_opt.1.load_ohm` = V / I of the source supply |
| `mat_opt.2.vout`, `.output` (puller supply) | `thermocouple.t1`..`t4` (degC) |

Model inputs, in this order in `config/plant.yaml`: `filament_current`, `rek_vset`, `rek_iset`,
`rek_on`, `gas_flow`, `shutoff_open`, `foreline_open`, `vent_open`, `cup_in`, `turbo_speed`,
`source_vset`, `source_iset`, `source_on`, `puller_voltage`, `puller_on`. A missing one is 0
(off, closed, stopped).

### Calibration: the owner's working point, and the pump's data

"Typical operating point: 8 V, 90 A on the filament, 150 V, 24 A on the discharge, pressure in the
6-way around 1e-5 Torr, MFC flow around 20 % open (at 5 SCCM max)." Later: "It could be that at
20% we were more in the 5e-5 Torr range, but the turbopump we have is a big one. I think it's a
1000C with a 250 ISO-K flange." The filament and discharge numbers and the flow are calibration
inputs (`wp_*`). The pumping speed comes from the pump's data sheet, so the pressure at the
working point is a PREDICTION, compared with the owner's range (`wp_cross_reading_low_torr`,
`wp_cross_reading_high_torr`), not fitted to it. At construction the model derives
(`PlantModel.derived`, also `info` on the plant's control port, printed by the step response tool):

| Derived | Value | How |
|---|---|---|
| hot filament resistance | 0.0889 ohm | 8 V / 90 A (the TDK simulator's load is 0.089 ohm) |
| filament power | 720 W | 8 V x 90 A |
| plasma limit at the point | 60 A | `plasma_margin` x 24 A: the point is emission limited |
| emission at the point | 24.5 A | 24 A = smooth minimum of emission and plasma limit |
| filament temperature | 2820 K | Richardson emission x area = 24.5 A, with the area that 720 W holds at T by radiation |
| filament area | 6.7 cm2 | as a check: a tungsten hairpin of 1.36 mm x 15.6 cm has 0.089 ohm hot |
| pumping speed for H2 | 1171 l/s | 1150 l/s N2 (data sheet) x 1.018 (H2/N2, estimate) |
| true H2 pressure in the cross | 1.52e-5 torr | (outgassing + 1 sccm) / pumping speed |
| nAIM reading, PREDICTED | 7.0e-6 torr | true pressure x `aim_h2_factor` (0.46) |
| plasma constant k | 0.074 A/V^1.5 | plasma limit at 150 V and the chamber pressure at 1 sccm |

The pump: Leybold, Operating Instructions GA 05.118/14.02 (05/2005), "TURBOVAC 35 LS ... 1000 C",
section 1.3 Technical Data, TURBOVAC 1000 C with 250 ISO-K inlet: pumping speed N2 1150 l/s,
36,000 rpm (600 Hz, now the `rated_speed_hz` of the `nt20_*` simulators), run-up time with the
frequency converter about 9 min. The table gives no He or H2 speed for the 1000 C; the H2/N2
ratio is taken from the TURBOVAC 600 C in the same table (570 / 560). Copy used:
https://www.ajvs.com/library/Turbovac%2035_to_1000c_Manual.pdf. The pump model itself is the
owner's "I think".

What the point implies:

- **The REK is at its current limit.** 24 A is the full scale of the REK150-24. With the limit at
  24 A, the model sits at the edge of constant current: more filament current cannot raise the
  discharge current, the voltage falls instead (149.2 V at the point). A discharge current loop
  through the filament current only acts downward here; it needs a set point below 24 A or a
  supply with more current (REK150-55). The model does not hide this.
- **The predicted pressure is BELOW the owner's range.** The model predicts a nAIM reading of
  7.0e-6 torr at 1 sccm, a factor 1.4 under the low end of 1e-5 to 5e-5 torr. Possible reasons,
  none chosen: the gauge sits on a side flange, away from the pump;
  a conductance between pump and chamber (ISO-K flange, valve, screen) lowers the effective
  speed below the data sheet value; the remembered flow; a different pump; the base pressure
  (a free choice of 2e-6 torr reading). The gauge calibration is not among them any more: the
  owner believes the nAIM is calibrated for N2 (2026-11-21), which is what the model assumes
  (H2 factor 0.46). If the gauge showed true hydrogen pressure, the reading would be
  1.5e-5 torr, inside the range.
- **It is one point.** The slopes around it (discharge current per filament current, per sccm)
  follow from Richardson's law, Stefan-Boltzmann and the free choices; they are properties of the
  model. `tools/plant_step_response.py` says so in its output.

### Equations (model.py, in this order every step)

```
Filament     P_f   = I_f^2 R(T)                    R(T) = R_hot (T / T_hot)^r_exp
             T_eq  = (P_f / (eps sigma A) + T_room^4)^(1/4)        Stefan-Boltzmann
             dT/dt = (T_eq - T) / filament_tau                     (thermal lag)
             I_e   = emission_factor  A_G T^2 exp(-W / kT)  A      Richardson-Dushman
Gas          Q     = gas_flow (only with the shutoff valve open) + burst        [sccm]
             V_ch dp_ch/dt   = Q - C_ap (p_ch - p_x)                         plasma chamber
             V_x dp_x/dt     = Q + Q0 + C_vx p_fl - (S + C_vx) p_x           cross
             V_fl dp_fl/dt   = S p_x + Q_fl + C_vent (p_atm - p_fl) - S_rough (p_fl - p_ult)
                               C_vent only with the vent valve open (it vents the turbopump),
                               S_rough = 0 with the foreline valve closed
             S     = S_turbo (f_stop + (1 - f_stop) speed / rated) / (1 + p_x / p_lim)
             nAIM  = aim_h2_factor p_x          APG = p_x within [apg_floor, apg_ceiling]
             Q0, p_ult: chosen so that the pumped, gas-free plant reads today's constants
Discharge    I_plasma(V) = k (V - V_min)^1.5 (p_ch - p_min) / (p_ch - p_min + p_half)   0 below V_min or p_min
             I_dis(V)    = (I_e^-n + I_plasma^-n)^(-1/n)            emission limit, smooth min, plasma limit
             REK on the load I_dis(V) + V / R_bleed: CV at vset if that draws <= iset, else CC at the V
             where it draws iset. The plant writes R = V / I: the REK simulator's own CV/CC logic
             then lands on that point, and its current limit keeps working.
Extraction   I_beam = beam_fraction I_dis (1 - exp(-(V_src + V_puller) / V_sat))  only with both on
             source supply on the load I_beam(V) + V / R_leak, same CV/CC rule; R = V / I written
             cup current = I_beam with the cup in (valve s4), else 0
Heat         t1 back plate        = base + back_plate_k   (P_f + P_dis)           lag plate_tau
             t2 filament feedthr. = base + feedthrough_k  P_f                     lag plate_tau
             t3 transformer 1     = base + rise (P_TDK / 2400 W)^2                lag transformer_tau
             t4 transformer 2     = base + rise (P_REK / 3600 W)^2                lag transformer_tau
             water t1..t7         = base + water_fraction (P_f + P_dis) / (rho c_p flow)   lag water_tau (no reader)
```

The thermocouple relations, chosen: the back plate faces the plasma and the filament, so it
warms with both powers; the feedthrough carries the filament current and conducts heat from the
filament, so it warms with the filament power only; each isolation transformer warms with the
power it carries (copper losses, square of the load), transformer 1 feeding the TDK and
transformer 2 the REK (which transformer feeds which supply is a free choice). All lags are
integrated exactly for a constant input over one step, so any `dt` is stable. The time
constants of the heat are minutes on a real source; the defaults (20 s, 40 s, 60 s) are chosen
so that a desk session sees an effect within a minute. Change them in `config/plant.yaml`.

### Disturbances: the plant's control port (6090, JSON lines as on a simulator)

```
{"cmd": "get"}                                     model state, inputs, links
{"cmd": "get", "signal": "foreline_pressure"}      one value (also filament_temperature, emission,
                                                   discharge_current, cross_pressure, beam_current, ...)
{"cmd": "info"}                                    signal names and the calibration (derived)
{"cmd": "set", "signal": "emission_factor", "value": 0.8}          emission -20 % at once
{"cmd": "set", "signal": "emission_drift_per_min", "value": -0.05} emission falls 5 %/min
{"cmd": "set", "signal": "pressure_burst_sccm", "value": 2}        extra gas, decays (burst_tau_s)
{"cmd": "release", "signal": "emission_factor"}                    back to neutral
```

`ControlClient("172.30.0.30", 6090)` works as on a simulator (`get`, `set`, `release`, `info`).

### Not modelled

Space charge and plasma physics beyond the two limits; the arc and filament burn-out at high
pressure; the cusp magnets; heating of the filament by the discharge; filament evaporation and
ageing (only as `emission_drift_per_min`); gas consumption by the discharge; outgassing that
rises with temperature; the gas dependence of the APG (Pirani); turbopump stall from a high
foreline pressure, and the run-down of the turbopump when it is vented (the NT 20 simulator
decides its speed); the roughing pump (always running); the cooling water flows; the lens
supplies and the puller current; beam transport (every extracted ion reaches the cup); the MFC
seeing its shutoff valve closed (it reports its own flow); the cold-junction channels j1..j4;
gauge heads switched off (the nAIM simulator still decides what it reports when off).

### Parameters (config/plant.yaml, section model)

| Parameter | Default | Unit | Source |
|---|---|---|---|
| `wp_filament_voltage_v` | 8 | V | owner's working point, 2026-11-21: filament 8 V |
| `wp_filament_current_a` | 90 | A | owner's working point, 2026-11-21: filament 90 A |
| `wp_discharge_voltage_v` | 150 | V | owner's working point, 2026-11-21: discharge 150 V |
| `wp_discharge_current_a` | 24 | A | owner's working point, 2026-11-21: discharge 24 A (the full scale of the REK150-24) |
| `wp_cross_reading_low_torr` | 1e-05 | torr | owner's working point, 2026-11-21: 'around 1e-5 Torr' in the six-way cross (nAIM reading); compared with the model, not used by it |
| `wp_cross_reading_high_torr` | 5e-05 | torr | owner's working point, 2026-11-21 (second answer): 'it could be that at 20% we were more in the 5e-5 Torr range'; compared with the model, not used by it |
| `wp_gas_sccm` | 1 | sccm | owner's working point, 2026-11-21: MFC about 20 % of 5 sccm H2 |
| `filament_tau_s` | 1 | s | free choice: 'about a second, which matches a thermal filament' (plan/controls.yaml, software.loops) |
| `filament_r_exponent` | 1.2 | 1 | law (fit): tungsten resistivity rises about as T^1.2 between 300 and 3000 K |
| `filament_emissivity` | 0.3 | 1 | law (tabulated): total emissivity of tungsten near 2800 K |
| `room_temperature_k` | 293 | K | free choice |
| `richardson_a_per_cm2_k2` | 60 | A/(cm2 K2) | law (tabulated): Richardson constant of tungsten |
| `work_function_ev` | 4.54 | eV | law (tabulated): work function of tungsten |
| `discharge_v_min_v` | 25 | V | estimate: no discharge below this voltage (H2 ionisation 15.4 V plus margin) |
| `discharge_exponent` | 1.5 | 1 | law (shape only): space-charge limited current rises as V^1.5 (Child-Langmuir) |
| `discharge_p_min_torr` | 0.0002 | torr | estimate: no discharge below this source pressure |
| `discharge_p_half_torr` | 0.001 | torr | estimate: the plasma limit is half its maximum at p_min + p_half |
| `discharge_smooth_n` | 3 | 1 | free choice: sharpness of the transition from emission limit to plasma limit |
| `plasma_margin` | 2.5 | 1 | free choice: at the working point the plasma could carry 2.5 times the discharge current, so the point is emission limited, which a loop on the filament current needs |
| `rek_bleed_ohm` | 10000 | ohm | free choice: a bleeder across the REK output, so that its current limit always has a load to act on |
| `sccm_to_torr_l_s` | 0.01267 | torr l/s per sccm | law: definition of the sccm (760 torr, 0 degC) |
| `aperture_conductance_l_s` | 8 | l/s | estimate: molecular flow of H2 through an extraction aperture of about 5 mm |
| `chamber_volume_l` | 1 | l | estimate: plasma chamber of the source |
| `cross_volume_l` | 40 | l | estimate: CF 10 inch six-way cross (three tubes of about 20 cm diameter, 60 cm long) |
| `aim_h2_factor` | 0.46 | 1 | law (tabulated, approximate): an ionisation gauge calibrated for N2 reads H2 at about 0.4 to 0.5 of the true pressure. That the nAIM is calibrated for N2 is the owner's belief (2026-11-21), not checked on the gauge |
| `cross_base_reading_torr` | 2e-06 | torr | free choice: the nAIM simulator's constant today (rack.yaml), base reading with the pump at speed and no gas |
| `apg_floor_torr` | 0.001 | torr | free choice: the lower limit of the simulator channel gauges.p1 (rack.yaml); a Pirani gauge shows nothing below about that |
| `apg_ceiling_torr` | 944.06 | torr | free choice: the upper limit of the simulator channel gauges.p1 (rack.yaml) |
| `turbo_speed_n2_l_s` | 1150 | l/s | law (data sheet): Leybold TURBOVAC 1000 C, 250 ISO-K inlet, N2 (GA 05.118/14.02, 1.3 Technical Data); the pump model is the owner's 'I think it's a 1000C with a 250 ISO-K flange' |
| `turbo_h2_n2_ratio` | 1.018 | 1 | estimate: the data sheet gives no H2 speed for the 1000 C; ratio H2/N2 of the TURBOVAC 600 C in the same table (570 / 560 l/s) |
| `turbo_stopped_fraction` | 0.01 | 1 | estimate: what a stopped turbopump still pumps (through to the foreline) |
| `turbo_p_limit_torr` | 0.01 | torr | estimate: inlet pressure at which the turbopump has lost half its speed (data sheet: max. permanent inlet pressure 1e-3 to 1e-2 mbar) |
| `foreline_base_torr` | 0.03 | torr | free choice: the APG simulator's constant before phase 1 (no foreline gauge in the control system yet) |
| `foreline_volume_l` | 2 | l | estimate: turbopump outlet, foreline up to the foreline valve |
| `rough_speed_l_s` | 5 | l/s | estimate: roughing pump (make and model not known) |
| `foreline_outgas_torr_l_s` | 0.001 | torr l/s | estimate: outgassing of the foreline |
| `vent_conductance_l_s` | 1 | l/s | estimate: vent valve on the side port of the turbopump, into the foreline side |
| `vent_cross_conductance_l_s` | 1e-05 | l/s | estimate: vent gas reaching the cross back through the turbopump; 'the inflow of N2 is small' (owner) |
| `atmosphere_torr` | 760 | torr | law |
| `burst_tau_s` | 2 | s | free choice: decay of a pressure burst set through the plant's control port |
| `beam_fraction` | 0.0002 | A/A | estimate: extracted beam current per A of discharge current at saturation (24 A -> 4.8 mA, within the 15 mA source supply) |
| `extraction_v_sat_v` | 8000 | V | estimate: the beam current rises as 1 - exp(-V / v_sat) with the extraction voltage (source + puller) |
| `source_leak_ohm` | 2e+08 | ohm | free choice: leakage of the source supply output, 100 uA at 20 kV |
| `plate_tau_s` | 20 | s | free choice: minutes in reality, short so that a desk session sees an effect within a minute |
| `back_plate_k_per_w` | 0.01 | K/W | estimate: t1, back plate, warms with filament + discharge power (about 4.3 kW at the working point -> 43 K) |
| `back_plate_base_c` | 41 | degC | free choice: the constant of thermocouple t1 today (hv.yaml) |
| `feedthrough_k_per_w` | 0.03 | K/W | estimate: t2, filament feedthrough, warms with the filament power only (720 W -> 22 K) |
| `feedthrough_base_c` | 38 | degC | free choice: the constant of thermocouple t2 today (hv.yaml) |
| `transformer_tau_s` | 60 | s | free choice: tens of minutes in reality, short so that a desk session sees an effect |
| `transformer_rise_k` | 40 | K | estimate: rise of an isolation transformer at the full rating of the supply it feeds; copper losses go with the square of the load |
| `transformer1_rated_w` | 2400 | W | free choice: transformer 1 (t3) feeds the filament supply, rating of the TDK GEN8-300 (8 V x 300 A) |
| `transformer2_rated_w` | 3600 | W | free choice: transformer 2 (t4) feeds the discharge supply, rating of the REK150-24 (150 V x 24 A) |
| `transformer1_base_c` | 35 | degC | free choice: the constant of thermocouple t3 today (hv.yaml) |
| `transformer2_base_c` | 33 | degC | free choice: the constant of thermocouple t4 today (hv.yaml) |
| `water_tau_s` | 40 | s | free choice: minutes in reality, short so that a desk session sees an effect within a minute |
| `water_flow_l_min` | 1 | l/min | estimate: within 0.25 to 2 l/min per branch (plan/controls.yaml) |
| `water_heat_fraction` | 0.3 | 1 | estimate: share of the heat power each sensor box channel sees (which sensor sits where is not known) |
| `water_cp_j_per_kg_k` | 4186 | J/(kg K) at 1 kg/l | law: heat capacity of water |
| `water_base_c` | t1 24, t2 25, t3 26, t4 27, t5 28, t6 29, t7 30 | degC | free choice: the constants of the sensor box simulator today (rack.yaml) |
