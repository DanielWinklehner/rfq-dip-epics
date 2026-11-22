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
| Records in `iocHV` (`EPICS/Db/loop.db`) | Interface: everything the operator sees and sets. Backstop: the only writer of the actuator (`_write`) and the watchdog of the service (`service:get`) | The actuator is written only in PID, at most once per period (0.2 s), by at most `slew x DT` per write, never away from `[outmin, outmax]` (after a limit moved past it, it is brought to the new limit at the slew rate), and never again after someone else wrote it. PID needs the service alive: when its counter stands still for the watchdog time, the mode goes to MANUAL, the request is cleared, the reason says "service stopped", `service:get` is 0 with MAJOR alarm. At an IOC start the mode is MANUAL |
| Service `loops/mist2loop` | The algorithm and the judgement: PID, anti-windup, bumpless switching, every check of section 4, the decision to hand back or refuse, the terms and flags shown | Hands back (or refuses) with the reason; follows the actuator in MANUAL; starts in MANUAL; ends in MANUAL on SIGTERM |

The service is only a Channel Access client of `iocHV` on the same computer. A client alone has
none of the trouble of two servers on one host (a unicast search reaching only one of them).

**The backstop, with plain records.** `_target` (calc) computes the next actuator value:
`_out` (what the service asks for) clamped to `[outmin, outmax]`, then the actuator's present set
point moved towards it by at most `slew x DT`. So the value lies between the present set point
and a point within the limits: inside the limits when the actuator is, closer to them when a
limit was moved past it. `_write` (calcout, scanned every `SCAN`) sends it to the actuator only
while `_mode` is 1, `outmin < outmax`, it differs from the present set point by `RES` or more,
and the present set point is still the value `_write` sent last (operator priority; at the first
scan in PID that value is taken from the actuator). `_mode` = request AND service alive AND accepted by the service. `service:get`
(calc, every 0.1 s) counts the seconds since `_count` last changed; `_dead` (calcout, CP links)
fires `_drop` (seq: request 0, accepted 0, reason "service stopped") when the service is not
alive while PID is requested or accepted. Test B proves this with the service stopped and a test
client writing wrong values in its place.

**Permits that are lost.** A Channel Access link to a PV that disconnects neither processes its
record nor reaches a calculation (dbCa does not process on a disconnect; calc skips its
expression when an input fails). So each permit condition is read by `_cN` (ai, CP, and scanned
every period), which turns INVALID (LINK) at its next scan when its link is lost or has never
connected; `_sN` (calc) makes 0, 1 or 2 of it, `permitN:get` (mbbi) the words. The REK's own
gate reads its permit the same way (`REK-1:_permit:read`, `rek.db`). `iocHV` sets
`EPICS_CA_CONN_TMO` to 5 s (our choice, default 30 s), so a silent rack IOC is noticed after
about 10 s (5 s, then an echo that is not answered within 5 s). Against it: on a congested
network a slow peer would be disconnected and reconnected more often; on the fiber between two
computers we see no such load. MEAS, ACT and HB must be records of `iocHV` itself (a link in one
IOC cannot be lost, and the writer's PP link must reach the actuator directly). Measured (test
B): the rack IOC stopped, hand-back "permit 1 no data" after 0.5 to 0.7 s and the REK off after
0.4 to 0.6 s; paused, 6.6 to 10 s for both.

## 2. The algorithm (`loops/mist2loop/pid.py`, no EPICS)

```
u = Kp*e + I - Kd*d(pv_f)/dt        e = sp - pv        I += Ki*e*dt
```

- Parallel form. The derivative acts on the measurement through a first-order filter (time
  constant `dfilter`), not on the error: a set point step does not kick the output.
- The output is clamped to `[outmin, outmax]`, then its change to `slew x dt`.
- **Anti-windup: conditional integration.** The integral takes `Ki*e*dt` only as far as the
  output stays within its limits; while the slew limit holds the output back in the direction of
  that step, only as far as the output really moves (P + I + D then equals the output sent); and
  it stays itself within `[outmin, outmax]`. So with a persistent error the output never stands
  still between its limits: it moves at the slew rate, or slower when the terms ask for less.
  And the integral is never ahead of the output sent: after a long time at a limit (output or
  slew) the output leaves it as soon as the terms ask for less. (Until the review of 2026-11-22
  the integral took no step at all at the slew limit: with `Ki*e` larger than the slew rate, the
  output then stood still after a bumpless start, review point F8.)
- **Bumpless.** At MANUAL to PID the integral is set so that the first output equals the
  actuator's present set point. A change of Kp or Kd moves the integral by the change of its
  term (no jump); Ki is inside the integral (no jump). A set point change moves the output by
  Kp times the change, a limit change moves it towards the new limit, both through the slew
  limit.
- **dt** from the monotonic clock between two cycles. `dt <= 0` (or not a number): nothing
  changes. `dt` longer than three periods: integrated as three periods, and the filter starts
  again (no derivative kick over the gap).
- The service writes `_out` every cycle, and counts `_count` only when a cycle has completed:
  a service whose cycles fail stops counting and the watchdog takes the mode back (the error is
  logged once, not every cycle). The IOC's writer applies the actuator's resolution
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
| `LOOP-DIS:permit1:get`, `permit2:get`, `permit3:get` | mbbi | Each permit condition as words: "fulfilled", the condition's words (W1 to W3: "interlock open", "REK not on in remote", "TDK output off"; no alarm, an off supply is normal), "no data" (INVALID: its PV INVALID, not connected or never connected) |
| `LOOP-DIS:limit:get` | mbbi | free, at minimum (MINOR), at maximum (MINOR), slew limited |
| `LOOP-DIS:value:setpoint` | ao | Set point, A, clamped to `[spmin, spmax]` |
| `LOOP-DIS:spmin:setpoint`, `spmax:setpoint` | ao | Set point limits (settings). Moved inside the present set point, they bring it to the limit; the loop follows through its slew limit |
| `LOOP-DIS:value:read` | ai | The measured value as the loop reads it (INVALID with its source) |
| `LOOP-DIS:output:get` | ai | Output, A: in PID the service's output, in MANUAL the TDK's set point |
| `LOOP-DIS:error:get`, `p:get`, `i:get`, `d:get` | ai | Error (A) and the three terms (A) |
| `LOOP-DIS:kp:setpoint` ... `watchdog:setpoint` | ao | Settings, section 5 |
| `_mode`, `_active`, `_count`, `_out`, `_target`, `_write`, `_dead`, `_drop`, `_c1`..`_c3`, `_s1`..`_s3`, `_act`, `_hb` | | Internal: mode logic, the service's acceptance, counter and output, the writer, the watchdog's drop, the permit conditions read and their state, mirrors of the actuator and of the heartbeat |

Registry roles (`plan/controls.yaml`, class `loop`): `mode_cmd`, `mode`, `reason`, `service`,
`permit1`..`permit3`, `limit`, `pv`, `out`, `error`, `pterm`, `iterm`, `dterm`, `sp_cmd`, `spmin`,
`spmax`, `kp`, `ki`, `kd`, `dfilter`, `outmin`, `outmax`, `slew`, `stale`, `watchdog`.

## 4. Hand-back and refusal

A hand-back in PID: MANUAL, the request back at MANUAL, the TDK keeps its last set point, the
reason is shown. A request for PID is refused (request back at MANUAL, reason shown, nothing
written) for the same reasons. The service checks in this order and reports the first.

| Reason (`reason:get`) | Who | How | Time limit (test B) |
|---|---|---|---|
| interlock open / REK not on in remote / TDK output off (R4 a) | service | `permitN:get` = 1 | 1 s (interlock box polled at 10 Hz) / 2.5 s (output state polled every 1 s) |
| permit N no data (R4 b) | service | `permitN:get` "no data" (INVALID): its PV INVALID (the interlock box silent), not connected (the rack IOC stopped or silent) or never connected (`iocHV` started while the rack IOC is down) | INVALID: 3 s (libcom1 timeout 1 s); connection closed: 2 s (one scan of `_c1`); peer silent: 13 s (`EPICS_CA_CONN_TMO` 5 s and an echo) |
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
| `spmax:setpoint` (set point maximum) | 23 | A | free choice, below the REK150-24's 24 A full scale (there the REK goes into constant current and the loop could only act downward); leaves 22 A a little room. TO BE CONFIRMED by the owner |
| `spmin:setpoint` | 0 | A | free choice. Keep `spmin < spmax`: with `spmin >= spmax` neither the set point record nor the service clamps the set point, which is then unbounded (within what the output limits allow) |
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

Last run (2026-11-22, after the second review (F8, F9); emulation with the plant model, default settings of section 5). A run
writes the table to `emulation/build/loop-plant.md`; the pass limits and where each comes from
are in `emulation/tests/loop_plant.py`. Properties of the MODEL, not of MIST-2.

| Closed loop on the plant model (LOOP-DIS) | Result | Pass limit |
|---|---|---|
| MANUAL to PID: discharge moved / first set step | 0.018 A / 0.014 A | 0.20 A / 0.20 A |
| Step 20.0 to 22.0 A: rise time 10-90 % | 1.80 s | 3.0 s |
| overshoot | 0.7 % | 10 % |
| settling time into +-0.10 A | 4.05 s | 6.0 s |
| steady-state error (mean of the last 5 s) | +0.0013 A | +-0.03 A |
| Emission drift -5 %/min, 30 s: largest deviation | 0.034 A | 0.30 A |
| deviation at the end of the drift | 0.018 A | 0.15 A |
| emission back at once: back into the band after | 1.24 s | 6.0 s |
| Output maximum lowered to 88.93 A in PID: TDK set / output:get / flag / mode | 88.93 A / 88.93 A / at maximum / PID | 88.93 A / the same / at maximum / PID |
| maximum restored at 20.397 A: lowest discharge current after / settled after | 20.337 A / 3.64 s | not below 20.297 A (no bump down) / 12.0 s |
| Unreachable (REK limit 21 A): TDK set / flag / highest set | 90.00 A / at maximum / 90.00 A | 90.00 A / at maximum / 90.00 A |
| limit restored: leaves the maximum after the error changed sign / settles after | 0.12 s / 2.24 s | 2 periods + 0.5 s / 12.0 s |
| PID requested at 18.00 A, set point 22 A (TDK 88.19 A): TDK first raised after / band reached after | 0.48 s / 6.98 s | 2 periods / 10 s |
| overshoot / largest TDK step | 0.5 % / 0.200 A | 10 % / 0.20 A (slew x DT) |
| Hand-back in closed loop (REK silent): reason / TDK set at the hand-back, 5 s later | permit 2 no data / 89.435, 89.435 A | measurement or permit 2 no data / the same |
| TDK current read-back at the hand-back, 5 s later | 89.47, 89.44 A | within 0.5 A (noise) |
| Writes per second to the TDK in PID (during the step) | 1.05 | at most 5 |
| TDK current read-back rate, MANUAL / PID | 10.00 / 10.00 per s | PID >= 90 % of MANUAL |
| REK current read-back rate, MANUAL / PID | 10.00 / 10.00 per s | (reported) |
| Closed loop on the plant model (LOOP-DIS) | Result | Pass limit |

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
