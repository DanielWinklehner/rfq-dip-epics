# Edwards TIC station: read-only (task T29)

The Edwards TIC controller ("the Edwards TIC station") as PVs: `EPICS/Db/tic.db` with the
protocol `EPICS/Db/tic.proto` (StreamDevice), the simulator `edwards_tic`
(`emulation/sim/mist2sim/devices/edwards_tic.py`), the device case `emulation/devtest/tic`, and
a probe for the first contact without an IOC, `EPICS/ioc/host/edwards_tic_probe.py`.

**Read-only.** Nothing here sends a command or a setup message (`!C`, `!S`) to the controller:
the probe, the protocol file and the database only query. Starting or stopping a pump, switching
a gauge or changing a setting from EPICS is not possible with these files. It waits until it is
known what the station runs.

What is read: the three gauge sockets (pressure and state of each gauge), the turbo pump (state,
type, speed), the backing pump (state, type), and what the controller says about itself
(identity string, software version, and the variant). What is not read: relays, set points,
the vent valve, heater band, air cooler, gauge types and names, gauges 4 to 6 of a 6-gauge
controller, power and temperatures, anything of a pump routed through the TIC (objects 800+).

No IOC of the emulation loads `tic.db` yet; the lead adds it after acceptance.

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
  the number format, the turnaround (20 ms), the identity string, that a command is answered
  `*C<obj> 1` and not executed.

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
6. Whether starting and stopping pumps from EPICS is wanted later.
