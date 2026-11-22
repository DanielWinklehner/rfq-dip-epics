# Control loops: design and operation

The first loop holds the **discharge current** of the source (`REK-1:current:read`) at its set
point through the **filament heating current** (`TDK:current:setpoint`). Its prefix is
`LOOP-DIS`. Work package WP10, step 1 (`plan/controls.yaml`).

**Owner's decisions (2026-11-22).** The PID runs in a Python service with pyepics; the loop's own
records are plain records in the platform IOC `iocHV`, without C code. The set point is 22 A
("set point below 24 A for now. 22 oughta do it."), below the 24 A full scale of the REK150-24,
until the REK150-55 is there. The platform PC runs a light Ubuntu variant, version not known.

Every number below that comes from the plant model is a property of the MODEL
(`emulation/sim/config/plant.yaml`), not of MIST-2.

## 1. Two layers

```
 operator (GUI, caput) ──► LOOP-DIS:*:setpoint ───┐
                                                  │        iocHV (EPICS/Db/loop.db)
 REK-1:current:read ──CP──► value:read ───────────┤  ┌──────────────────────────────────┐
 interlock_open, REK, TDK ──► permit1..3:get ─────┼─►│ records: interface and backstop  │
 TDK:current:setpoint ──CP──► _act ───────────────┤  │ _target, _write ──► TDK set point │
                                                  │  │ service:get (watchdog), _drop     │
                     Channel Access, monitors     │  └──────────────────────────────────┘
                                                  ▼               ▲ _out, _active, _count,
                     loops/mist2loop (Python): PID, checks, ──────┘ mode, reason, terms
                     hand-back and refusal
```

| Layer | What it does | What it guarantees on its own |
|---|---|---|
| Records in `iocHV` (`EPICS/Db/loop.db`) | Interface: everything the operator sees and sets. Backstop: the only writer of the actuator (`_write`) and the watchdog of the service (`service:get`) | The actuator is written only in PID, at most once per period (0.2 s), only within `[outmin, outmax]`, by at most `slew x DT` per write, never from a set point outside the limits, and never again after someone else wrote it. PID needs the service alive: when its counter stands still for the watchdog time, the mode goes to MANUAL, the request is cleared, the reason says "service stopped", `service:get` is 0 with MAJOR alarm. At an IOC start the mode is MANUAL |
| Service `loops/mist2loop` | The algorithm and the judgement: PID, anti-windup, bumpless switching, every check of section 4, the decision to hand back or refuse, the terms and flags shown | Hands back (or refuses) with the reason; follows the actuator in MANUAL; starts in MANUAL; ends in MANUAL on SIGTERM |

The service is only a Channel Access client of `iocHV` on the same computer. A client alone has
none of the trouble of two servers on one host (a unicast search reaching only one of them).

**The backstop, with plain records.** `_target` (calc) computes the next actuator value:
`_out` (what the service asks for) clamped to `[outmin, outmax]`, then the actuator's present set
point moved towards it by at most `slew x DT`. `_write` (calcout, scanned every `SCAN`) sends it
to the actuator only while `_mode` is 1, `outmin < outmax`, the value lies within the limits, it
differs from the present set point by `RES` or more, and the present set point is still the
value `_write` sent last (operator priority; at the first scan in PID that value is taken from
the actuator). `_mode` = request AND service alive AND accepted by the service. `service:get`
(calc, every 0.1 s) counts the seconds since `_count` last changed; `_dead` (calcout, CP links)
fires `_drop` (seq: request 0, accepted 0, reason "service stopped") when the service is not
alive while PID is requested or accepted. Test B proves this with the service stopped and a test
client writing wrong values in its place.

## 2. The algorithm (`loops/mist2loop/pid.py`, no EPICS)

```
u = Kp*e + I - Kd*d(pv_f)/dt        e = sp - pv        I += Ki*e*dt
```

- Parallel form. The derivative acts on the measurement through a first-order filter (time
  constant `dfilter`), not on the error: a set point step does not kick the output.
- The output is clamped to `[outmin, outmax]`, then its change to `slew x dt`.
- **Anti-windup: conditional integration.** The integral takes `Ki*e*dt` only as far as the
  output stays within its limits, not at all while the slew limit holds the output back in the
  direction of that step, and stays itself within `[outmin, outmax]`. After a long time at a
  limit the output leaves it as soon as the error changes sign.
- **Bumpless.** At MANUAL to PID the integral is set so that the first output equals the
  actuator's present set point. A change of Kp or Kd moves the integral by the change of its
  term (no jump); Ki is inside the integral (no jump). A set point change moves the output by
  Kp times the change, a limit change moves it towards the new limit, both through the slew
  limit.
- **dt** from the monotonic clock between two cycles. `dt <= 0` (or not a number): nothing
  changes. `dt` longer than three periods: integrated as three periods, and the filter starts
  again (no derivative kick over the gap).
- The service writes `_out` every cycle. The IOC's writer applies the actuator's resolution
  (`RES` 0.01 A: the TDK takes two decimals, `PC %.2f` in `tdk.proto`).
- A second loop: one more `dbLoadRecords` line of `loop.db` in `iocHV/st.cmd` and one more prefix
  in `loops/config/mist2.yaml`. No name of the discharge loop is in the Python code or the template.

**Where the neural network would attach (not built, no records for it).** As one more part of
the service: gain scheduling would write `kp`, `ki`, `kd` (the settings records, so the operator
sees them), a feed-forward term would be added to `u` before the limits. Its output passes the
same limits in the service and the same backstop in the IOC; a bad or late answer means plain PID.

## 3. Records (prefix `LOOP-DIS`, all in `iocHV`)

| PV | Type | Meaning |
|---|---|---|
| `LOOP-DIS:mode:setpoint` | bo | Request MANUAL / PID. Set back to MANUAL by the service (hand-back, refusal) and by the IOC (service not alive): latched, nothing returns to PID by itself. Not saved |
| `LOOP-DIS:mode:get` | bi | Mode: PID only while requested, accepted by the service and the service alive |
| `LOOP-DIS:reason:get` | mbbi | Last hand-back or refusal, as words, until the next request (section 4) |
| `LOOP-DIS:service:get` | calc | 1: the service's counter changed within the watchdog time; 0 (MAJOR) else |
| `LOOP-DIS:permit1:get`, `permit2:get`, `permit3:get` | calc | Each permit condition, DESC names it: 0 fulfilled, 1 not (MAJOR), 2 no data (INVALID) |
| `LOOP-DIS:limit:get` | mbbi | free, at minimum (MINOR), at maximum (MINOR), slew limited |
| `LOOP-DIS:value:setpoint` | ao | Set point, A. Its DRVL and DRVH are the set point limits (settings) |
| `LOOP-DIS:value:read` | ai | The measured value as the loop reads it (INVALID with its source) |
| `LOOP-DIS:output:get` | ai | Output, A: in PID the service's output, in MANUAL the TDK's set point |
| `LOOP-DIS:error:get`, `p:get`, `i:get`, `d:get` | ai | Error (A) and the three terms (A) |
| `LOOP-DIS:kp:setpoint` ... `watchdog:setpoint` | ao | Settings, section 5 |
| `_mode`, `_active`, `_count`, `_out`, `_target`, `_write`, `_dead`, `_drop`, `_act`, `_hb` | | Internal: mode logic, the service's acceptance, counter and output, the writer, the watchdog's drop, mirrors of the actuator and of the heartbeat |

## 4. Hand-back and refusal

A hand-back in PID: MANUAL, the request back at MANUAL, the TDK keeps its last set point, the
reason is shown. A request for PID is refused (request back at MANUAL, reason shown, nothing
written) for the same reasons. The service checks in this order and reports the first.

| Reason (`reason:get`) | Who | How | Time limit (test B) |
|---|---|---|---|
| interlock open / REK not on in remote / TDK output off (R4 a) | service | `permitN:get` = 1 | 1 s (interlock box polled at 10 Hz) / 2.5 s (output state polled every 1 s) |
| permit N no data (R4 b) | service | `permitN:get` = 2: its PV INVALID or not connected | 3 s (libcom1 timeout 1 s) |
| measurement no data (R4 b) | service | `value:read` INVALID | 2 s (REK at 10 Hz, timeout 150 ms) |
| actuator no data (refusal only) | service | `_act` INVALID before PID | 1 s |
| measurement stale (R4 c) | service | `_hb` (the IOC's heartbeat) unchanged for longer than `stale:setpoint` | stale time + 1.5 s, not before stale time - 1.2 s |
| written by someone else (R4 d) | service, and the writer stops by itself | a value of the TDK set point that `_write` did not send | 1 s |
| set not accepted (R4 e) | service | `_act` INVALID in PID (the TDK's set ended INVALID) | 1 s |
| outside output limits (refusal only) | service | TDK set point outside `[outmin, outmax]`, or `outmin >= outmax` | 1 s |
| service stopped (R4 f, R5) | IOC alone | `_count` unchanged for `watchdog:setpoint`: `_dead`, `_drop`; also when the service ends on SIGTERM | watchdog + 0.5 s |
| IOC start (R4 g) | IOC | the request is not saved, `reason:get` starts at "IOC start" | - |
| service start (R4 g) | service | at its first contact it clears request and acceptance | - |

What the time limits come from: the poll periods in `tdk.db`, `rek.db`, `interlockbox.db`, the
reply timeouts in the protocol files, the service's cycle (0.2 s) and the watchdog scan (0.1 s);
`emulation/tests/test_09_loop.py` states each. When the platform IOC goes away (its container
stopped, or the computer), the service's monitors stop: the heartbeat looks stale and the loop
records are disconnected; the IOC itself is gone, so nothing writes the actuator.

## 5. Settings (`iocHV/limits.defaults`, saved by autosave in `limits.sav`)

| Setting | Default | Unit | Source |
|---|---|---|---|
| `value:setpoint` | 22 | A | owner, 2026-11-22 |
| `value:setpoint.DRVH` (set point maximum) | 23 | A | free choice, below the REK150-24's 24 A full scale (there the REK goes into constant current and the loop could only act downward); leaves 22 A a little room. TO BE CONFIRMED by the owner |
| `value:setpoint.DRVL` | 0 | A | free choice |
| `kp:setpoint` | 0.5 | A/A | model, ASSUMED: SIMC for gain 3.56 A/A (the model's steepest point), time constant 1.45 s, dead time about 0.3 s (TDK 0.1 s, plant step 0.1 s, polling and the period), closed-loop time constant 0.5 s: Kp = tau / (K (tau_c + theta)) |
| `ki:setpoint` | 0.35 | A/A/s | model, ASSUMED: Ki = Kp / tau |
| `kd:setpoint` | 0 | A s/A | model: a first-order plant needs no derivative |
| `dfilter:setpoint` | 0.2 | s | free choice (one period) |
| `outmin:setpoint` | 80 | A | free choice: below the model's 12 A point (85.8 A), the filament stays hot |
| `outmax:setpoint` | 90 | A | owner's working point (2026-11-21): the loop never heats more than the owner runs |
| `slew:setpoint` | 1 | A/s | free choice: about 3 A/s of discharge current in the model |
| `stale:setpoint` | 3 | s | free choice: three missed counts of the heartbeat (once per second) |
| `watchdog:setpoint` | 2 | s | free choice: ten missed cycles of the service |
| Period (`SCAN`, `DT`, `period_s`) | 0.2 | s | bus arithmetic and model, below |
| `RES` (macro) | 0.01 | A | `tdk.proto`: the TDK takes the current with two decimals |
| Output limit range (`OLO`, `OHI`, macros) | 0 to 300 | A | the TDK GEN8-300's rating |

**Period.** The model's time constant is 1.45 s, its dead time about 0.3 s: 0.2 s is a seventh of
the time constant, well inside the dead time. The TDK line (19200 baud, 10 bits per character)
carries the polls of `MV?` and `MC?` at 10 Hz and three status polls per second: about 23
transactions per second of 10 to 11 ms each (characters plus 5 ms turnaround, assumed A6), about
25 % of the line. A set (`PC 89.44` and `OK`) takes about 11 ms; at the most one per period, 5 per
second, it adds 5.5 %. Measured on the plant (test C): 1 write per second during a set point
step, and the TDK's read-back rate the same in MANUAL and in PID (10.0 per second).

## 6. Results on the plant model (test C, `make -C emulation test-loop`)

See `emulation/build/loop-plant.md` after a run; the table of the last run is in the report of
T15. Pass limits and their sources are in `emulation/tests/loop_plant.py`.

## 7. Tuning on the machine

The gains above are the model's. On the machine:

1. In MANUAL, at a steady discharge current a little below the set point (for example 20 A),
   step the TDK current by +0.3 A (about 1 A of discharge current in the model; keep it small,
   the filament is a hairpin). Log `REK-1:current:read` at 10 Hz (or `camonitor`).
2. Read from the response: the gain K (change of the discharge current over 0.3 A), the dead
   time theta (until it starts to move) and the time constant tau (two-point method: tau = 1.5
   (t63 - t28), theta = t63 - tau, as in `emulation/sim/tools/plant_step_response.py`). Repeat at
   the set point (22 A): the gain rises steeply with the working point (Richardson); use the
   largest gain.
3. Gains (SIMC, closed-loop time constant tau_c, start with tau_c = theta, slower if noisy):
   `Kp = tau / (K (tau_c + theta))`, `Ki = Kp / min(tau, 4 (tau_c + theta))`, `Kd = 0`.
4. Check in PID with a set point step of 0.5 A: overshoot under 10 %, settling within a few tau.
   Raise `slew` only when the filament allows it.
5. Write the results into `EPICS/ioc/iocBoot/iocHV/limits.defaults` (autosave keeps the running
   values anyway).

## 8. Operating

- Switch: `caput LOOP-DIS:mode:setpoint 1` (PID), `0` (MANUAL). Read `LOOP-DIS:mode:get` and
  `LOOP-DIS:reason:get`.
- Before PID: interlock closed, REK on in remote, TDK on, the TDK set point within the output
  limits, the service alive (`LOOP-DIS:service:get` 1).
- The operator has priority: writing `TDK:current:setpoint` in PID hands back, and the IOC does
  not write it again.
- Service: `loops/README.md` (emulation: container `loop`; platform computer: systemd unit
  `loops/systemd/mist2loop.service`, Python 3.8 or later, pyepics in a virtual environment; NOT
  VERIFIED on the real computer, whose Ubuntu variant and version are not known).

## 9. Not built

- The neural-network step (section 2), and any record for it.
- A second loop.
- A GUI widget for the class `loop` (next task); the GUI shows a generic widget meanwhile.
- The installation on the platform computer (only written, not tried).
- Measured gains: everything in section 5 marked model or free choice needs the machine.
