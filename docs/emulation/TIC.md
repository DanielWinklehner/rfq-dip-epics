# Edwards TIC station (tasks T29, T31, T32)

The Edwards TIC controller ("the Edwards TIC station") as PVs: `EPICS/Db/tic.db` (read only,
T29) and `EPICS/Db/tic_control.db` (three requests, T32, section "Control" below) with the
protocol `EPICS/Db/tic.proto` (StreamDevice), the simulator `edwards_tic`
(`emulation/sim/mist2sim/devices/edwards_tic.py`), the device cases `emulation/devtest/tic`
(`tic.db` alone) and `emulation/devtest/tic_control` (both files), and a probe for the first
contact without an IOC, `EPICS/ioc/host/edwards_tic_probe.py`.

**`tic.db` is read only.** It sends nothing but queries, and its device case shows it. The
commands are in `tic_control.db`, loaded beside it with the same port: the cart's backing pump
and turbopump on and off, the AIM on socket 2 on and off, each one command, each only when an
operator writes the request. No file here sends a setup message (`!S`). The probe sends queries
only.

What is read: the three gauge sockets (pressure and state of each gauge), the turbo pump (state,
type, speed), the backing pump (state, type), and what the controller says about itself
(identity string, software version, and the variant). What is not read: relays, set points,
the vent valve, heater band, air cooler, gauge types and names, gauges 4 to 6 of a 6-gauge
controller, power and temperatures, anything of a pump routed through the TIC (objects 800+).

The rack IOC loads `tic.db`, `tic_control.db` and the three take-overs of `first_contact.db`
(`iocBoot/iocRack/st.cmd`); so does the emulation.

## Sources

| Document | From | Used for |
|---|---|---|
| Edwards, *Turbo Instrument Controller (TIC) Serial Communications*, D397-30-880 Issue H (2012). Covers all seven variants: TIC Instrument Controller (D397-00-000), 6-Gauge (D397-01-000), 6-Gauge Capacitance Manometer (D397-02-000), TIC Turbo Controller 100/200 W (D397-11/12-000), TIC Turbo & Instrument Controller 100/200 W (D397-21/22-000) | `https://www.lesker.com/newweb/Gauges/pdf/tic-instrument-controller-serial-communications.pdf` | every message, object, reply field and state word |
| Edwards, *Instruction Manual, Turbo Controller*, D397-12-880 Issue E (2007), TIC Turbo Controller 100 W and 200 W | `https://mmrc.caltech.edu/Vacuum/Edwards/EXPT%20Pumping%20Station/Edwards%20TIC%20controller.pdf` (a university's copy) | connector, pins, cable, line settings, factory defaults |
| Edwards, *Quick Start Guide*, D397-10-880 Issue F | `https://www.lesker.com/newweb/Gauges/pdf/tic-instrument-controller-quick-start-guide.pdf` | only that the same seven variants exist; it has no line settings |
| Edwards, product data sheet *TIC Turbo and Instrument Controller* | `https://www.lesker.com/newweb/Gauges/pdf/tic-turbo-instrument-controller-datasheet.pdf` | that this variant has the same RS232/485 9-way 'D' socket |

**Not read:** the instruction manuals of the TIC Instrument Controller (D397-00-000) and of the
TIC Turbo & Instrument Controller (D397-21/22-000). The copies found were refused to an automated
download (`idealvac.com` sent an HTML page instead of the PDF, `manuals.online` answered 403;
`scribd.com` and `manualslib.com` need a login and were not tried). The *TIC PC program*
manual D397-11-880 was not read either (same site). So the line settings below come from the
Turbo Controller's manual only; that the other variants use the same is an assumption (A-T29-1).

Places below are those of D397-30-880 unless another document is named.

## Connection

| What | Value | Place |
|---|---|---|
| Connector | 9-way sub-miniature 'D' socket on the rear panel | D397-12-880 2.4.5, 3.3.8.1 |
| Pins | 2 RS232 transmit, 3 RS232 receive, 5 RS232 common, 8 RS485 A, 9 RS485 B, others not connected | D397-12-880 Table 6 |
| Cable | a "straight through" male-female 9-way extension cable to a PC's 9-way socket; shielded; RS-232 shorter than 10 m. Edwards sells a 2 m RS232 cable D397-00-834 | D397-12-880 3.3.8.1, accessories |
| Line | 9600 baud, 8 data bits, no parity, 1 stop bit, Xon/Xoff; no hardware handshake | D397-12-880 2.4.5, 3.3.8.1 |
| Messages | every message ends with CR; the TIC answers only when asked, one message at a time | 1.2 |
| Factory setting | PC comms RS232, multi-drop address 0 | D397-12-880 Table 15 |
| Reply time | basic messages less than 100 ms; suggested master timeout 500 ms | 1.4 |

A USB-serial adapter on the rack computer. The port file sets the line (lines for the lead
below), including `ixon` for Xon/Xoff: with it the serial driver takes an Xon or Xoff character
from the TIC instead of handing it to StreamDevice, where it would break a reply.

RS-485 multi-drop (a prefix `#dd:ss` before each message, 1.6.1) is not built. Room for it: the
macro `PROTO` of `tic.db` names the protocol file, so a second protocol file with the prefix can
be loaded without touching the database.

## The probe (first contact, IOC stopped)

```
EPICS/ioc/host/edwards_tic_probe.py /dev/ttyUSB0
```

Python 3 standard library only, as `matsusada_probe.py`. It opens the device at 9600 8N1 with
Xon/Xoff, sends each of these queries once, waits up to 500 ms for each (`--timeout`), and
prints one line per query: the query, what it asks for, the raw reply, the time to the end of the
reply, and what it means. The last line says how many of the ten were answered. Exit code 0:
all ten answered, 1: not, 2: the device cannot be opened.

| Query | Asks for | Reply form | Place |
|---|---|---|---|
| `?S902` | identity | `=S902 TIC;Dxxxxxxxx;serial number;PIC s/w ver` | Table 1, 1.6.2.2 |
| `?V902` | system status | one state per item, then alert ID and priority; the number of fields tells the variant: TC 7, IC 8, TIC 10, IC6 14 | Table 1, object 902 |
| `?V913` `?V914` `?V915` | gauge 1, 2, 3 | `=V913 value;units type;state;alert ID;priority` | Table 1 |
| `?V904` | turbo pump state | `=V904 state;alert ID;priority` | 1.6.2.3 |
| `?S904 3` | turbo pump type | `=S904 3;type` | 1.6.2.3 |
| `?V905` | turbo speed | `=V905 value;alert ID;priority`, 0.0 - 110.0 % | Table 1 |
| `?V910` | backing pump state | `=V910 state;alert ID;priority`, state 0 - 4 | Table 1 |
| `?S910 3` | backing pump type | `=S910 3;type` | Table 1 |

An error reply `*V904 2` is an answer: the probe prints its meaning from Table 3 (1 "Invalid
command for object ID", 2 "Invalid query/command", ...). That is what to expect from a query to
an object the controller does not have; the manual does not say which code. `NO REPLY`: nothing
came within the timeout (check the cable, the device, the line settings, and that the controller
is set to RS232). `NOT THE FORM THE PROTOCOL FILE EXPECTS`: the IOC would not read this reply;
please send the output.

A gauge line prints the pressure in torr only when the units type is 59 and the state 11 (On),
for example `1.000e-06 torr (1.3332e-04 Pa), state 11 On, units 59 pressure, Pa, alert 0,
priority 0`. Otherwise it prints the raw value and the state word, e.g. `state 0 Gauge Not
connected`.

Test of the probe, without a controller: `python3 EPICS/ioc/host/edwards_tic_probe_test.py`.

## PVs (macro DEVICE, default TIC; asyn port macro PORT, default TIC)

| PV | Type | Unit | Scan | What |
|---|---|---|---|---|
| `TIC:gauge1:getpressure` (also `gauge2`, `gauge3`) | calc | torr | 1 s | pressure of gauge n. Valid only if the reply has units type 59 and gauge state 11 (On); otherwise INVALID and NaN |
| `TIC:gauge1:state:get` | mbbi | | 1 s | gauge state, the words of 1.7.7: Gauge Not connected, Gauge Connected, New Gauge Id, Gauge Change, Gauge In Alert (MAJOR), Off, Striking, Initialising, Calibrating, Zeroing, Degassing, On, Inhibited; for an error reply the words of Table 3 (INVALID); "No valid reply" (INVALID) |
| `TIC:gauge1:units:get` | mbbi | | 1 s | units type of the reply, 1.7.4: PRESSURE (Pa), VOLTAGE (MAJOR), PERCENT (MAJOR) |
| `TIC:gauge1:alert:get` | longin | | 1 s | alert ID, 1.7.3 (0 No Alert, 6 No Gauge, 14 Not Struck ...) |
| `TIC:gauge1:priority:get` | mbbi | | 1 s | 1.7.2: OK, warning (MINOR), alarm (MAJOR) |
| `TIC:turbo:state:get` | mbbi | | 2 s | 1.7.8: Stopped, Starting Delay, Stopping Short Delay, Stopping Normal Delay, Running, Accelerating, Fault Braking (MAJOR), Braking; "No Pump" (pump type 0) and error replies INVALID |
| `TIC:turbo:type:get` | mbbi | | 2 s | 1.7.11: No Pump, EXDC Pump, EXT75DX Pump, EXT255DX, Mains Backing Pump, Serial Pump, nEXT - 485, nEXT - 232, nXDS, Not yet identified |
| `TIC:turbo:speed:get` | calc | % | 2 s | turbo speed; INVALID and NaN when there is no pump |
| `TIC:turbo:alert:get` | longin | | 2 s | alert ID of the turbo pump |
| `TIC:backing:state:get` | mbbi | | 2 s | 1.7.6 without the last word "State": Off, Off Going On, On Going Off Shutdown, On Going Off Normal, On; "No Pump" and error replies INVALID |
| `TIC:backing:type:get` | mbbi | | 2 s | as `turbo:type:get` |
| `TIC:backing:alert:get` | longin | | 2 s | alert ID of the backing pump |
| `TIC:variant:get` | mbbi | | 2 s | TC, IC, TIC or IC6, from the number of fields of `?V902` |
| `TIC:ident:get` | lsi | | 2 s | the identity string of `?S902`, up to 80 characters |
| `TIC:model:get` | stringin | | with ident | first field of the identity ("TIC") |
| `TIC:sw:get` | stringin | | with ident | second field: software version |

`model:get` and `sw:get` read the replies that `ident:get` asks for (SCAN I/O Intr, as
`AIM:_enable:get`): they keep their last value while the controller is silent, when `ident:get`
is INVALID. Internal records start with `_` (`gauge1:_q` holds the fields of the last reply:
A value, B units, C state, D alert, E priority, F the code of an error reply).

Every record is INVALID while the controller does not answer, answers an error, or answers in
another form. In the device case this took 3.1 s for all records after the simulator fell
silent, and 1.2 s back to valid after it answered again.

## One polling cycle

Every second, each of the three gauge records sends `?V913` (`?V914`, `?V915`) and waits up to
120 ms for the reply. Before the request it sets its fields to "nothing" (NaN, -1). The reply's
five fields go into the record; then `_ok` decides whether this is a pressure of a gauge that
is on, `getpressure` converts pascal to torr (1 torr = 101325/760 Pa) or gives NaN, and the
state, units, alert and priority records follow.

Every 2 seconds one chain runs, one query at a time: `?V902` (variant), `?S902` (identity),
`?S904 3` (turbo type), `?V904` (turbo state), `?V905` (speed), `?S910 3` (backing type),
`?V910` (backing state), each record handing over to the next when its reply is in or its
timeout is over.

## Rate

ReplyTimeout is 120 ms, ReadTimeout 50 ms (`tic.proto`). Every 2 s the line carries 13 queries
(6 gauge queries, 7 others).

| Case | Per query | 13 queries | Fits 2 s? |
|---|---|---|---|
| Controller silent | request 6 - 8 characters at 9600 baud (8 ms) + 120 ms timeout | 1.66 s | yes |
| Slowest answers the manual allows | about 34 characters (35 ms) + 100 ms turnaround + 16 ms USB latency | 1.95 s at most | yes |
| Measured in the device case (simulator, 20 ms turnaround) | | 6.50 requests/s, line busy 31.9 % | |
| Measured, silent simulator | 121.4 ms per query (IOC log) | 1.58 s | yes |

The gauges alone need 3 x 128 ms = 0.38 s of each second at worst. With the manual's suggested
500 ms timeout a silent cycle would need 13 x 0.508 = 6.6 s; that is why 120 ms is used. If the
real TIC answers in more than about 100 ms, the probe's times show it and the timeout must grow,
or the 2 s chain must shrink.

## The variants

| Object | TIC (Turbo & Instrument) | TC (Turbo) | IC (Instrument, 3 gauges) | IC6 (6 gauges) |
|---|---|---|---|---|
| `?V902` fields | T;B;G1;G2;G3;R1;R2;R3;alert;priority (10) | T;B;R1;R2;R3;alert;priority (7) | G1;G2;G3;R1;R2;R3;alert;priority (8) | G1..G6;R1..R6;alert;priority (14) |
| Gauges 913-915 | yes | no gauge in its status | yes | yes; 934-936 too |
| Pumps 904, 905, 910 | yes | yes | no pump in its status | no pump in its status |

From Table 1, object 902 (the structures per unit type), and object 931 (default screens per
type). The manual does not say what a controller answers to an object it does not have. The
records treat any error reply `*V<obj> <code>` as "not on this controller": INVALID, with the
word of Table 3. The simulator answers code 2 then (an assumption, option `absent_code`).
What the identity string of an IC or a TC starts with is not given (1.6.2.2 shows "TIC" only).

## Control (task T32)

The owner, 2026-11-25: "yes, I want to start and stop the pumps from the GUI", and for the AIM
on socket 2, which the TIC did not switch by itself: "definitely through the GUI too", with his
rule "The AIMs may not be turned on until the APG shows 1e-2 Torr or lower".

### What is sent

| Request (bo) | 1 | 0 | Command | Seen on the lab's TIC (2026-11-25, by hand) |
|---|---|---|---|---|
| `TIC:backing:start:set` | run | stop | `!C910 1` / `!C910 0` | both, each answered `*C910 0` after 19 ms; the state 4 at the next query (32 ms), 0 after 25 ms, nothing between |
| `TIC:turbo:start:set` | run | stop | `!C904 1` / `!C904 0` | both, each `*C904 0` after 19 ms; the old state still at 32 and 51 ms; 0, 5 Accelerating to about 50 %, 4 Running, 100 % after 120 s; down 7 Braking to 0.3 %, then 0, 105 s with the backing pump off right after the stop (more than 5 minutes with the backing pump left on) |
| `TIC:gauge2:on:set` | on | off | `!C914 1` / `!C914 0` | **never sent**: D397-30-880 Table 1 object 914 ("On/off"), 1.7.5 "Gauge On = 1, Gauge Off = 0". At the panel: 5 Off to 11 On in one step at a 1 s scan, then one standing value for 146 s (P74); 11 to 5 in one step |

Each write is one command and nothing else: no sequence, no setup, no retry. The protocol
`command` of `tic.proto` sends the bo's value and expects `*C<obj> 0`; that ends the request
without alarm. Any other code leaves the request INVALID (CALC) and `...:reason` shows the code's
word of Table 3; no reply leaves it INVALID (TIMEOUT), the reason "No reply". The pump's state in
the IOC is the TIC's own, so a failed request does not change it.

The socket of the switched gauge is a macro (`SOCKET=2`, `OBJ=914` in the st.cmd).

### What is read back

| PV | From | Means |
|---|---|---|
| `TIC:turbo:start:get` | `TIC:turbo:state:get` (every 2 s) | run in 1 Starting Delay, 5 Accelerating, 4 Running (the states that follow a start); stop in the others; INVALID while the state is not known |
| `TIC:turbo:atspeed:get` | `TIC:turbo:speed:get` | at speed from 95 % (macro `ATSPEED`); not the state Running, which the TIC shows from 50 % |
| `TIC:backing:start:get` | `TIC:backing:state:get` | run in 1 Off Going On and 4 On |
| `TIC:gauge2:on:get` | `TIC:gauge2:state:get` (every 1 s) | on in 6 Striking and 11 On |
| `TIC:<...>:reason` | each request | Acknowledged, a Table 3 word, No reply, No valid reply, a refusal's word, or "No request since start" |
| `TIC:gauge2:slave:get` | `?S914 4` every 10 s | "linked" (the TIC switches the gauge by itself at the set points: `:slave:on:get`, `:slave:off:get` in torr, `:slave:master:get` the master's object) or "not linked"; INVALID with "No valid reply" for a reply of another form, whose text `TIC:gauge2:slave:raw` keeps |

The slave setup's reply has not been seen for a gauge: the form is the one the lab's TIC gave
for the turbopump (`?S904 4` -> `=S904 4;0;59;0.0000e+00;0.0000e+00;0`, 56 ms). The manual's own
example has no config type (`=S904 913;59;5.1e-2;4.9e-1;1`); such a reply is INVALID here and
its text kept. The probe reads both gauges' setups with the IOC stopped:
`edwards_tic_probe.py <device> --query "?S913 4" --query "?S914 4"` (queries only: anything else
is refused before the port is opened, exit code 3).

### What the IOC refuses, and how it says so

| Request | Refused while | Reason's word |
|---|---|---|
| `TIC:turbo:start:set` := 1 | the backing pump is not On (state 4); or its state is not known | "Refused: backing not on"; "Refused: backing unknown" |
| `TIC:backing:start:set` := 0 | the turbopump is in a state that follows a start (1, 5, 4); or its state is not known | "Refused: turbopump runs"; "Refused: turbo unknown" |
| `TIC:gauge2:on:set` := 1 | the APG's pressure (`TIC:gauge1:getpressure`) is above 1e-2 torr (macro `PMAX`); or not valid | "Refused: APG > 1e-2 torr"; "Refused: APG not valid" |

A refused request sends nothing: the request is INVALID (LINK) at once, falls back 0.02 s later
to the read-back's value (in simulation mode, as the take-over at the first contact does) and is
then without alarm; its reason says why. Stops and switch-offs are never refused, except the
backing pump's while the turbopump runs. In the run-down (7 Braking) the backing pump may be
stopped: the order used on 2026-11-25 (turbopump stop, backing pump off right after) held.

How (the header of `tic_control.db` has the details): the request's disable link SDIS reads a
calc `_refuse` with PP and MS before the record support runs; a refusal is an INVALID alarm of
that calc, which MS makes the request's own, and with IVOA "Don't drive outputs" the bo does not
call StreamDevice. DISV is -1, so the request is never disabled.

### What is not built, by decision

- No pressure condition for the turbopump's start (the owner has given none, question 26 b).
- No sequence ("system on"), no setup message, no procedure for spin-up or shut-down (a later
  task, the owner's word).
- No refusal of the turbopump's stop with the foreline valve open: the GUI's confirmation warns
  while `VALVE:s1:get` reads open or is not known (the owner: "No, but pop up a warning").
- No communication timeout, no automatic stop: a pump keeps its state when the IOC stops or loses
  the line. An IOC start sends nothing: each request takes over the station's state at the TIC's
  first answer (`first_contact.db`).
- The IOC does not switch the AIM off when the pressure rises: that is the TIC's own slave setup
  to do, which the IOC reads. An automatic action needs the owner's word.
- No refusal of a turbopump start while it still brakes (not tried on the controller; see
  "Assumed").

### The simulator

`edwards_tic` executes the commands as the lab's TIC was seen to: the replies after the
turnaround (20 ms; 19 ms seen), the backing pump in its new state at once, the turbopump's state
and speed over time along the curves seen (options `turbo_runup`, `turbo_rundown_backing_off`,
`turbo_rundown_backing_on`, points [seconds, %]; a change of the backing pump during a run-down
moves it onto the other curve), the old state for `turbo_delay_s` after a command. The gauge: on
by `!C91x 1` or the panel (signal `g<n>.panel`), `strike_s` in Striking, then `standing_s` (146 s)
one standing value, then the pressure; off at once. Its slave setup (option `slave`) is what
T31's option `switch` was: in the emulation's configuration not linked (the lab's TIC waited for
the panel), linked in a unit test and in the device case. The emulation's AIM starts On. The
signal `command_code` makes every command get an error code; the fault `silent` gives none.

## Assumed

- A-T29-1: The line settings, connector and cable of the Turbo Controller manual (D397-12-880)
  hold for the station's variant. The serial manual is the same for all seven.
- A-T29-2: The gauge value of `?V913` is in pascal whenever the units type is 59, whatever the
  front panel shows (1.7.4: "PRESSURE 59 - float (Pascals only)"; "Pressure values used in the
  configuration setups and in the logging will be in Pascals"). The display unit (object 929) is
  not read. A gauge in voltage mode answers 66 and is INVALID.
- A-T29-3: The backing pump states are those of 1.7.6 (Table 1 says "State 0 - 4" for object
  910 and names no table). A value outside 0 - 4 makes `backing:state:get` INVALID.
- A-T29-4: A query to an object the controller does not have gets an error reply (code not
  known).
- A-T29-5: ReplyTimeout 120 ms suffices (the manual: basic messages less than 100 ms).
- The simulator: the value of a gauge that is not on (9.9e9, from the example of object 940),
  the number format, the turnaround (20 ms), the identity string, that a setup message or a
  command to another object is answered `*<type><obj> 1` and not executed.
- Of T32, in the simulator only (named options in `config/rack.yaml`; the IOC does not depend on
  any of them):
  - `turbo_delay_s` 1.0 s: how long the turbopump's state stays the old one after a command
    (seen: more than 51 ms, and the new state at the next sample 5 s later).
  - `turbo_running_pct` 50.5 % (seen: 50.1 % Accelerating, 54.3 % Running; 49.5 % to about
    51 % on the second run) and `turbo_stopped_pct` 0.2 % (seen: 0.3 % Braking, 0.1 % Stopped).
  - the end of the run-down with the backing pump left on: 0 % after 600 s (seen: 0.7 % and
    still Braking after 5 minutes).
  - `start_without_backing: accept` (`!C904 1` with the backing pump off: not tried; the IOC
    refuses it) and `start_while_braking: accelerate` (a start during the run-down: not tried;
    the IOC does not refuse it, see the questions in the plan).
  - a gauge command to a socket without a gauge, or to a gauge in another state than 5, 6, 11:
    answered `*C91x 5`; `strike_s` 0.5 s (no Striking seen at a 1 s scan).
  - that `*C914 0` answers a gauge command, as for the pumps (the gauge command was not tried).

## Seen on the lab's controller (2026-11-25, by the lab session, reported to the development session)

The probe on the powered station, both pumps off, twice with the same replies, 10 of 10:

| Query | Reply | What it says |
|---|---|---|
| `?S902` | `=S902 TIC100;D39700640T;160070509<00>;5.0` | type "TIC100", software D39700640T, and a NUL byte after the serial number |
| `?V902` | `=V902 0;0;2;0;0;0;0;0;0;0` | 10 fields: a TIC Turbo and Instrument Controller |
| `?V913` | `=V913 9.9000e+09;59;2;9;0`, later `4.6208e+04;59;11;0;0` | socket 1: first "New Gauge Id" with alert 9 and no reading, then "On" with a value in pascal |
| `?V914`, `?V915` | `9.9000e+09;59;0;0;0` | sockets 2 and 3: no gauge connected |
| `?V904`, `?S904 3`, `?V905` | `0;0;0`, `3;3`, `0.0;0;0` | turbopump stopped, type 3 "EXT75DX Pump", speed 0 |
| `?V910`, `?S910 3` | `0;0;0`, `3;8` | backing pump off, type 8 "Mains Backing Pump" |

- **The NUL byte made `TIC:ident:get` INVALID** (seen with the simulator sending this form:
  "surplus input"). `tic.proto` ignores what follows the identity's text since that day, so the
  identity is type, software and serial number; the PIC software version is not read.
- **A newly plugged gauge is not read until it is accepted at the TIC's front panel:** socket 1
  stayed in the state "New Gauge Id" for more than two minutes and changed to "On" when the
  owner selected the gauge there. Until then `TIC:gauge<n>:getpressure` is INVALID and
  `TIC:gauge<n>:state:get` says "New Gauge Id".
- **A gauge that measures reports state 11 and units type 59, and its value is in pascal,
  whatever the display shows:** 4.62e4 Pa on the line while the display showed "460", and
  after the owner's atmosphere adjustment at the gauge exactly 1.0000e+05 on the line and
  "1000" on the display. So the display is in mbar and the line in pascal; the IOC shows
  750 torr for it. No state other than 11 was caught during the adjustment (sampled every 5 s).
- **Reply times** 23 to 50 ms, the identity 61 and 86 ms: the reply timeout is 150 ms (it was
  120 ms).
- **The adapter** is a Prolific PL2303 without a serial number: it is named by its USB socket.
- Not seen yet: the IOC on this controller, the pumps running, a gauge other than the APG.

## What is needed from the station to finish

1. Which variant: the label on the back (D397-00/01/02/11/12/21/22-000), or the probe's
   `?V902` line (number of fields) and `?S902` line.
2. What hangs on which gauge socket (1, 2, 3): which Edwards gauge (APG, AIM, WRG ...), and
   where it sits (six-way cross, foreline ...). Then the PVs get names of the lab's style
   (`PRESSURE:...:getpressure`) or aliases.
3. Which turbo pump and which backing pump the TIC runs, if any (the probe's pump type lines).
4. The probe's reply times (are they below 100 ms?).
5. Which USB-serial adapter connects it, for the device name in `ports.real.cmd`.
6. Whether starting and stopping pumps from EPICS is wanted later. **Answered (2026-11-25):
   yes, and the AIM too: section "Control".**
