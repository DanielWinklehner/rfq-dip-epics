# Picoammeter of the dipole scan (task T25)

The picoammeter of the dipole scan as PVs: `EPICS/Db/picoammeter.db` with the protocol
`EPICS/Db/keithley6485.proto` (StreamDevice), the simulator `keithley_6485`
(`emulation/sim/mist2sim/devices/keithley_6485.py`) and the device case
`emulation/devtest/picoammeter`. The plan names the instrument "Keithley, model tbc"
(`keithley_desk`, work package WP11). **The model is assumed: Keithley 6485 (assumption A44).**
Another model costs the protocol file and the simulator; the database names only the protocol
entries `poll`, `identify`, `zero_check`, `range` and the bad bits of the status word (macro
`BADBITS`).

No IOC of the emulation loads it yet; the device stays "later" in the plan.

## Source

Keithley, *Model 6485 Picoammeter Instruction Manual*, document 6485-901-01 Rev. A, November 2001,
`https://download.tek.com/manual/6485-901-01(A-Nov2001)(Instruction).pdf` (Tektronix download
site). Pages below are the manual's own (section-page). For the 6487: *Model 6487 Picoammeter /
Voltage Source Reference Manual*, 6487-901-01 Rev. D, October 2020,
`https://www.tek.com/-/media/documents/6487-901-01d_oct2020.pdf`.

## PVs (macro DEVICE, default pico1)

| PV | What |
|---|---|
| `pico1:current:get` | current in A. INVALID/STATE while the reading is no measurement (zero check on, overflow, overvoltage), with the last measured number kept; INVALID/TIMEOUT, CALC or the asyn alarm when the instrument is silent, answers something else, or the connection is closed |
| `pico1:range:set` | request: 0 AUTO, 1..8 = 2 nA, 20 nA, 200 nA, 2 uA, 20 uA, 200 uA, 2 mA, 20 mA |
| `pico1:range:get` | the range in use as the instrument reports it (also while autoranging) |
| `pico1:zcheck:set` | request: zero check OFF/ON |
| `pico1:zcheck:get` | zero check as reported |
| `pico1:nplc:get` | integration time in power line cycles |
| `pico1:idn:get` | `*IDN?` after "KEITHLEY INSTRUMENTS INC.,": "MODEL 6485, serial, firmware" (lsi, read as `idn:get.VAL$`) |

Internal: `_raw` (the poll, the reading as sent), `_zch`, `_rng`, `_auto`, `_nplc`, `_stamp`
(the reading's timestamp, s), `_status` (status word), `_ok`, `_valid`, `_hold`, `_zcheck`,
`_range:idx`, `_range:rb` (the value range:set takes over), and the records of first_contact.db.

Loading, as in the device case (`emulation/devtest/picoammeter/ioc.cmd`):

```
dbLoadRecords("db/picoammeter.db", "DEVICE=pico1,PORT=PICO")
dbLoadRecords("db/first_contact.db", "P=pico1,N=range,REQ=pico1:range:set,RB=pico1:_range:rb")
dbLoadRecords("db/first_contact.db", "P=pico1,N=zcheck,REQ=pico1:zcheck:set,RB=pico1:zcheck:get")
```

## Commands used, with their place in the manual

| Command | Use | 6485 manual |
|---|---|---|
| `ABOR` | first in every message: to idle, so that the commands after it are executed | 7-4 (Idle and initiate), Table 7-3 (7-9), 7-10 |
| `INIT` | after every message, as a message of its own: measuring again | Table 7-3 (7-9), 7-10 |
| `SYST:ZCH?`, `SYST:ZCH ON/OFF` | zero check read-back and request | Table 2-4 (2-15), Table 14-6 (14-8) |
| `CURR:RANG?`, `CURR:RANG 2E-9` ... `2E-2` | range read-back and fixed range | Table 4-2 (4-4), Table 4-3 (4-5), Table 14-4 (14-5) |
| `CURR:RANG:AUTO?`, `CURR:RANG:AUTO ON/OFF` | autoranging | Table 4-2 (4-4), Table 14-4 |
| `CURR:NPLC?` | integration time | Table 4-4 (4-6), Table 14-4 |
| `SENS:DATA?` | the last reading, without triggering one | Table 3-1 and A) (3-5), Table 14-4 |
| `*IDN?` | identity | Table 11-1 (11-2), A) (11-3) |

Message rules: several commands in one message, separated by ";", ":" after ";" back to the root
(9-14); an invalid command is not executed and the commands after it are ignored (9-15); several
answers come in order, separated by ";" (9-15, printed "0; 1; 1; 0"). Over RS-232 commands are
executed after CR (9-17); only ASCII data (13-4).

Replies: reading string with the default elements READing, UNITs, TIME, STATus ("All 4", Table
13-2, 13-3), Figure 13-1 (13-4): `+1.040564E-06A, +2.236299E+02, +1.380000E+02`. Overflow and
overvoltage readings are `+9.9E37` (13-6). Status word in decimal: bit 0 overflow, bit 7
overvoltage, bit 9 zero check, bit 10 zero correct (13-6, 13-7). `*IDN?`:
`KEITHLEY INSTRUMENTS INC., MODEL 6485, xxxxxxx, yyyyy/zzzzz/w` (11-3).

Not in the manual: the format of the answers to `CURR:RANG?` and `CURR:NPLC?` (parsed as any
number), whether `CURR:RANG?` reports the range in use while autoranging, whether `CURR:RANG`
alone switches autoranging off (the protocol sends `AUTO OFF` first), whether the blanks after
"," and ";" are really sent (both are parsed).

## Why every message starts with ABOR and ends with INIT

As shipped the instrument powers up to the factory setup (1-15; `SYST:POS` default PRES, Table
14-6), whose arm count is INF (Table 1-3, 1-16). In front panel operation it "immediately leaves
the idle state when it is turned on" and stays in the trigger model (7-4, Figure 7-1). "While
operating within the trigger model (not in idle), most commands will not be executed until the
instrument completes all of its programmed operations and returns to the idle state"; ABORt is
one of the commands that are executed (7-4). With an infinite count READ? cannot be used, the
manual's way is INITiate, ABORt, then SENSe:DATA? (12-3). So the instrument does not answer a
query at all in its power-on state unless the query follows ABOR.

ABOR and INIT change no setting: no range, no format, no reset. They stop the measuring for the
length of one message and start it again. The reading in progress at the ABOR is lost; the
last completed one is read. Consequences:

* a scan faster than one reading time gets no new reading at all (each ABOR kills the reading
  in progress): the device case showed it with SCAN .2 s (below).
* an instrument halted at its front panel (HALT key, 7-4) is started again by the next poll.
* in the bus setup (`*RST`, arm count 1) the INIT takes one reading per poll.
* `INIT` is a message of its own: when `SENS:DATA?` fails (error -230, no reading yet, 3-5), the
  rest of its message would be ignored (9-15), INIT with it, and the instrument would stay idle
  for good. The protocol also sends INIT after a timeout or a mismatching answer.

## A reading, step by step

1. `_raw` (SCAN 1 s) sends `ABOR;:SYST:ZCH?;:CURR:RANG?;:CURR:RANG:AUTO?;:CURR:NPLC?;:SENS:DATA?`
   and reads e.g. `0; 2.000000E-07; 1; 6.000000E+00; +1.234568E-07A, +1.234567E+03, +0.000000E+00`:
   the four settings into `_zch`, `_rng`, `_auto`, `_nplc`, the reading into its own value, the
   timestamp and status into `_stamp`, `_status`. Then it sends `INIT`.
2. `_ok` = 1 when `(status & 641) = 0` (no overflow, overvoltage, zero check) and |reading| < 9E36.
3. `_valid` (bi): INVALID/STATE when `_ok` is 0, else the communication alarm of `_raw`.
4. `_hold` takes the reading when valid, else keeps its value; `current:get` copies value and
   alarm (MSS). So overflow and zero check give INVALID/STATE with the last measured number,
   never 9.9E37.
5. The read-backs (`zcheck:get`, `range:get`, `_range:rb`, `nplc:get`) take their value from the
   answer and only the communication alarm of `_raw`.

Zero check at the time of the reading comes from the status word, not from `SYST:ZCH?`: right
after a change the last reading can still be one taken before it.

## First contact (an IOC start changes nothing)

No record sends a setting at the start: no `@init`, no PINI on a request. `idn:get` has PINI and
sends `ABOR;*IDN?` and `INIT`. The requests take over the instrument's state through
first_contact.db: `range:set` from `_range:rb` (0 while autoranging, else 1 + the range index),
`zcheck:set` from `zcheck:get`, at the first good poll after the start, in simulation mode, and
only if no client wrote the request before. Until then they stay INVALID/UDF. first_contact.db
names bo and ao as requests; `range:set` is an mbbo: its simulation mode is the same as the bo's
(`mbboRecord.c`, writeValue, EPICS 7.0.10 in the image: `sdly < 0` writes SIOL and finishes at
once), the copy writes a double into the mbbo's VAL. The device case checks that this works.

## State after power-on, and what an operator does before a reading means anything

Factory setup (Table 1-3, 1-16/1-17, the power-on setup as shipped): **zero check ON**, zero
correct OFF, range AUTO, rate SLOW: NPLC 6 at 60 Hz or 5 at 50 Hz, autozero ON (Table 2-2),
filters, REL and math off, arm count INF. With zero check on, the input is shunted (2-13, Figure
2-9): the reading is no measurement and `current:get` is INVALID/STATE.

Before a reading means anything (3-3, "Procedure"): connect with zero check on, optionally zero
correct on the range to be used (Step 2; not in this database, front panel ZCOR), choose a range
or AUTO (`range:set`), then **zero check OFF** (`pico1:zcheck:set` = OFF). Warm-up: one hour to
rated accuracy (2-2). The instrument must be on the RS-232 interface with the line settings of
the port file (front panel COMM, 9-3): it ships with GPIB selected (Table 1-3, "RS-232: Off at
factory").

The manual is not consistent about autoranging after power-on: Table 1-3 says AUTO for the
factory setup, the note of Table 14-4 says the `SYST:PRES` default of `RANG:AUTO` is OFF. The
IOC takes over whatever it finds; the simulator's option `power_on_auto` (default AUTO) chooses.

## Rate

One reading takes NPLC / f_line (4-5: 1 PLC = 16.67 ms at 60 Hz, 20 ms at 50 Hz), up to three
times that with autozero on (2-2: off "increases measurement speed up to 3 times"). After
power-on: T_r <= 3 x 6 / 60 Hz = 3 x 5 / 50 Hz = 0.3 s. One poll at 9600 baud: about 160
characters, 0.16 s. The scan period must exceed T_r plus the line time, 0.46 s, or polls find no
new reading. SCAN = 1 s (macro). With a higher NPLC: P > 3 x NPLC / f_line + 0.2 s. Measured in
the device case: 10 new readings in 10 s (1.000 Hz), timestamp steps 0.999 to 1.088 s, 2.2
messages per second on the line, line busy 17 %.

Alarm time: silent or wrong answers make every read-back INVALID within P + ReplyTimeout = 1.5 s
after the last good poll, 2 s if an identity request waits for its own timeout first (measured
0.7 to 1.8 s); valid again at the next good poll.

## The 6487

For the commands used, the 6487 reference manual (Rev. D) has the same: the trigger model rule
(7-4), the factory arm count INF and bus count 1 (default settings table, 1-10), range commands and
defaults (4-4), NPLC (4-6), `*IDN?` with "MODEL 6487" (11-2), the ASCII reading with overflow
+9.9E37 and the same status bits 0, 7, 9, 10 (13-6, 13-7). Differences that matter here:

* the default elements are "all except VSOurce" (13-3): the same four as the 6485 unless someone
  added the voltage source element, which would make `poll` mismatch (INVALID/CALC).
* the 6487 has an ohms function: with it on, the reading is in ohms and the unit element is
  "OHMS" (13-6): `poll` expects "A" and the reading is INVALID/CALC.
* the voltage source (`SOUR:VOLT`, interlock) is not covered.
* the RS-232 menu names the transmit terminator choices CR, LF, CRLF, LFCR (9-3).
So the same database and, apart from the model in `idn:get`, the same protocol serve a 6487
used as a picoammeter.

## Line settings (for the port file, not set here)

The manual names the choices, not the factory values: baud 300 ... 57.6k, 7 or 8 data bits, one
stop bit, parity none/odd/even, transmit terminator LF, CR, LFCR or CRLF, flow control none or
XON/XOFF; no hardware handshake; commands are executed after CR (9-16, 9-17; Appendix A, A-2,
"RS-232 IMPLEMENTATION"). DB-9, straight-through cable, TXD/RXD/GND (9-18, Table 9-2). The
power-up display shows the baud rate in use (1-14, "RS-232: 9600b" as an example). Assumed here:
9600 baud, 8 data bits, no parity, 1 stop bit, terminator CR both ways, no flow control; to be
read off the instrument's COMM menu.

## Unknowns

| Unknown | Effect | Who |
|---|---|---|
| the model (6485 assumed, A44) | another model: protocol and simulator | owner |
| the line: the plan says "RS-485 to USB converter", the 6485 has RS-232 (9-16) and GPIB | the port file; RS-485 needs a converter at the instrument | owner |
| the line settings in use (baud, bits, parity, terminator, flow) | port file and `Terminator` in the protocol | owner (COMM menu) |
| the power-on setup in use (FACT, USR0-2, GPIB) and what the LabVIEW program sets (elements, arm count, NPLC, zero check, filters, REL) | the poll expects the default elements; a changed element list gives INVALID/CALC | owner, LabVIEW program |
| response time of the instrument | ReplyTimeout 500 ms assumed | lab test |
| reply format of `CURR:RANG?`, `CURR:NPLC?`; the range reported while autoranging | parsed as any number; range:get | lab test |
| whether `CURR:RANG` alone switches autoranging off | the protocol sends AUTO OFF first | lab test |
| what remote commands over RS-232 do to the front panel (remote/local, `SYST:REM` exists, 13-8) | the operator's front panel use | lab test |
| autorange state after power-on (Table 1-3 vs Table 14-4) | none for the IOC (takes it over) | lab test |
| the exact time of a reading with autozero (factor up to 3) | the scan period's margin | lab test |
| what a reading shows with zero check on | none (INVALID) | - |
| whether the instrument answers the queries before a failing `SENS:DATA?` | a short answer: INVALID/CALC once | lab test |
