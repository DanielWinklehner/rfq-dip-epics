# The scan program (mist2scan)

A one-dimensional scan through Channel Access only: one actuator PV is stepped through a list of
points, detector PVs are recorded at each point. First use: the dipole scan, which the owner wants
off LabVIEW (owner, 2026-11-24; plan/controls.yaml, WP11). The emittance scanners (WP12) are to
use the same program. Code and how to run it: [../../scans/README.md](../../scans/README.md).

The program is a Channel Access client and nothing else. It talks to no device: the devices
become PVs in IOCs (the dipole supplies through the NI box: T24; the picoammeter: T25), so that
their values reach the logger and the GUI whether or not a scan runs, and there is one master per
device. It writes one PV, the actuator's set point, and only inside the limits.

## 1. Parts

| Part | Does | EPICS import |
|---|---|---|
| `definition.py` | Reads and checks the YAML definition, the point list, the part steps | no |
| `stats.py` | The statistics of one channel over one dwell | no |
| `engine.py` | Refusals, the points, every end, the exit codes | no |
| `files.py` | The scan's directory: `points.csv`, `scan.json`, `definition.yaml` | no |
| `ca.py` | pyepics: one monitored PV per name, fresh reads, control limits, the one write | yes |
| `__main__.py` | `run` and `check`, overrides, SIGINT/SIGTERM | (through ca.py) |

As in the loop service (`loops/`), the logic is tested without EPICS against a fake Channel
Access side with a fake clock (`scans/tests`), and the whole program against soft records in an
IOC (`emulation/devtest/scan`).

## 2. How it works

### Monitors and fresh reads

Every PV of the definition (set PV, read-back, detectors, conditions) is one `epics.PV` with
`form="time"` and a monitor, so that every update carries value, alarm severity and the IOC's
time stamp (pyepics 3.5.8 `pv.py`, `PV.__on_changes` passes them to the callback). The monitor
mask is pyepics' default `DBE_VALUE | DBE_ALARM` (`ca.py`, `DEFAULT_SUBSCRIPTION_MASK`): a change
of severity arrives even when the value stays. A lost connection calls the connection callback
with `conn=False` (`ca.py`, `_onConnectionEvent`). Callbacks run in Channel Access' own thread
(`ca.py`, `PREEMPTIVE_CALLBACK = True`); they only store what arrived, under a lock, with the
arrival time. A fresh read (`get_with_metadata(use_monitor=False)`) asks the IOC, not the cache.

A value is not used when its severity is INVALID, when its PV is not connected, when it has no
alarm state or is not a finite number. In this system a device that stopped answering turns its
records INVALID (`EPICS/README`, "Alarms"); the scan relies on that and does not try to judge
"stale" values by itself.

### One point, step by step

1. **Move.** The point is written to the set PV. If it is more than `max_step` away from the
   last value written, it is written in n equal part steps, none larger than `max_step`, with
   `step_pause` seconds between them; the last write is the point exactly.
2. **Settle.** Wait until the read-back is valid and within `tolerance` of the point, at most
   `settle_timeout` seconds from the last write. Not reached: the point is a row with outcome
   `not_settled` and every detector missing ("not settled", with the last read-back), then the
   scan goes on (`on_not_settled: skip`) or ends (`end`, exit code 7). Never a silent pass.
3. **Settle time.** Wait `settle_time` seconds more.
4. **Dwell.** Every channel (the read-back and each detector) is read fresh from the IOC; from
   then on every monitor update is collected for `dwell` seconds. Nothing that arrived before
   this step is used: the collection opens after the settle time, and the first value of each
   channel is the fresh read, not the cache.
5. **Row.** Per channel: time-weighted mean, spread, number of values, minimum, maximum, valid
   fraction, status (`ok`, `partial`, `missing`) and the reason. The row is written and flushed
   to disk (`fsync`) before the next point. The point's outcome is `ok`, or
   `readback_left_tolerance` when the read-back left the tolerance during the dwell.
6. A required detector `missing` at this point ends the scan (exit code 6) after the row.

While it waits (part step pauses, settling, settle time, dwell) the program checks every 50 ms:
a stop signal; the actuator (the set PV, the read-back and the held PV connected; the set PV not
INVALID: the IOC did not confirm the write; the held PV not INVALID: what the device holds is not
known; the read-back not without a valid value for longer than `readback_lost_after`, a shorter
INVALID stretch is waited out); every required detector connected; every condition holding
(connected, not INVALID, the comparison true). The first that fails ends the scan (section 5). A
point interrupted in this way has no row. (The held PV and `readback_lost_after`: T27, second
round.)

### What a dwell counts

A monitor delivers a value when it changes (or its alarm state does), not at a fixed rate.
Between two updates the PV holds its value: what the scan sees is a step function of time. The
mean of a step function over the dwell is its integral over the dwell divided by the dwell: the
mean of the values, each weighted by the time it held inside the dwell. That is the mean of the
quantity, whatever the update rate. An arithmetic mean of the updates would count a value that
held for 0.9 s the same as one that held for 10 ms, and make a detector that updates in bursts
look different from one that updates evenly. The spread is the time-weighted standard deviation
in the same sense. `n` is the number of valid values used: the fresh read plus every later update
(one whose IOC time stamp is newer than the fresh read's: the same processing is not counted
twice).

A detector that holds one value for the whole dwell sends no update: it is counted once, from
the fresh read at the start of the dwell (`n` 1, mean that value, spread 0, status `ok`). A
record with a monitor dead band (MDEL) posts only changes larger than it; the step function is
then right within the dead band.

Invalid stretches (an INVALID value, a disconnect) are left out of the weights; `valid` is the
fraction of the dwell with a valid value, the status `partial` and the reason says why. No valid
value in the whole dwell: the status is `missing`, mean, spread, minimum and maximum are `nan`,
`n` is 0, and the reason says why ("INVALID (STATE)", "not connected", "no answer"). An older
value is never carried into a point.

An INVALID value's reason names the alarm status the IOC gave, as the IOC names it
(`menuAlarmStat`: "INVALID (STATE)", "INVALID (TIMEOUT)", "INVALID (UDF)", ...), in `points.csv`,
in `scan.json` and in the refusals (T27, second round). Channel Access sends it with every value
of type DBR_TIME (status and severity of the TIME structure, pyepics 3.5.8 `dbr.py`
`_STAT_SEV_TS`; `ca.py` `_unpack_metadata` puts it into `md["status"]`; the monitor callback gets
it as the keyword `status`, `get_with_metadata(form="time")` as `md["status"]`). When it does not
come, the reason says "INVALID (status not delivered)"; a number beyond the table "INVALID (status
<n>)".

## 3. The definition, key by key

YAML. A key that is not listed here is an error, at every level (a misspelt `tolerence` must not
become a default). All numbers in the PV's own units (EGU of the set PV).

| Key | Required | Meaning |
|---|---|---|
| `name` | no | Name of the scan; the directory is `<name>-<date>-<time>` |
| `description` | no | Text, copied into `scan.json` |
| `actuator.set` | yes | The set PV: the only PV the program writes |
| `actuator.readback` | yes | The read-back PV, compared with the point |
| `actuator.held` | no | The PV that shows the value the device holds (the dipole: `dipole:current:held`). With it, refused when it is not connected or INVALID ("the value the device holds is not known") or differs from the set PV's value by more than the tolerance (both values named); during the scan and the end move, INVALID or not connected = the actuator lost |
| `actuator.readback_lost_after` | no | Seconds the read-back may be without a valid value (INVALID) before the actuator counts as lost (exit 5), during a point and during the end move; default 5, > 0. A shorter stretch is waited out. A read-back that disconnects is lost at once, as before |
| `actuator.tolerance` | yes | Settled when \|read-back - point\| <= tolerance, > 0 |
| `actuator.settle_timeout` | yes | Seconds from the last write until the read-back must be within the tolerance, > 0 |
| `actuator.settle_time` | yes | Seconds to wait after that, >= 0 |
| `actuator.max_step` | yes | Largest change per write; `null`: every move is one write |
| `actuator.step_pause` | yes | Seconds between part steps, >= 0 |
| `actuator.limits` | yes | `[minimum, maximum]`; the set PV's control limits (DRVL, DRVH) also apply |
| `actuator.on_not_settled` | yes | `skip` (record the point as not settled, go on) or `end` (exit code 7) |
| `points.start`, `.stop`, `.step` | one form | `start + k * step`; the step's sign must point to `stop`; `stop` is included when it lies on the grid (within 1e-9 of a step); values rounded to 12 significant digits |
| `points.values` | the other | An explicit list, in the order given |
| `detectors[].pv` | yes | A PV to record, at least one detector |
| `detectors[].name` | no | Column prefix (default: the PV name); not `readback`, no commas or quotes |
| `detectors[].required` | yes | `true`: refused at the start when not connected or INVALID, the scan ends when lost; `false`: missing values, the scan goes on |
| `dwell` | yes | Seconds per point to collect, >= 0 |
| `conditions[]` | no | `{pv, op, value}`, `op` one of `== != < <= > >=`. Must hold at the start and the whole time |
| `end` | yes | `previous` (the set PV's value before the scan), `stay`, or a number |
| `output` | no | Directory for the scan directories (default `scan-data`, relative to the working directory) |
| `connect_timeout` | no | Seconds to wait for the PVs at the start (default 5) |

Command line: `--start`, `--stop`, `--step` replace the point range (all three when the
definition lists values), `--dwell`, `--output`; `-v` logs every write.

`check` connects, reads and prints the points, the limits used, the actuator's value now, the
detectors, conditions, end, units and the time: at least the moves, settle times and dwells (a
lower bound: the settling is not counted, it is not known before), at most every point to its
settle timeout. It says whether the scan would start. It writes
nothing. Exit code 0 (would start) or 3 (would be refused).

## 4. Files

One directory per scan, `<output>/<name>-<YYYYmmdd-HHMMSS>` (local time; `-2`, `-3` when taken).

**points.csv**: comma separated, one header line, one row per point, written and flushed when the
point is done. Columns `point` (index), `time` (ISO 8601 with offset, at the end of the dwell),
`elapsed_s` (since the start), `set`, `outcome` (`ok`, `not_settled`, `readback_left_tolerance`),
then for `readback` and each detector name: `_mean`, `_spread`, `_n`, `_min`, `_max`, `_valid`,
`_status`, `_reason`. Missing numbers are `nan`. Read by `pandas.read_csv` and
`numpy.genfromtxt(..., delimiter=",", names=True, dtype=None, encoding="utf-8")` (the device case
reads it with numpy).

**scan.json**: written at the start with `"state": "running"` and replaced (atomically) at the
end; a scan killed hard (SIGKILL, power) still says `running`. Keys: program, version, python and
pyepics versions, host, command, definition file and the definition as it ran,
`EPICS_CA_ADDR_LIST`, `start_time`, `end_time`, `duration_s`, `state` (`completed`, `ended`),
`outcome` (`code`, `reason`, `detail`, the `point` and `phase` it ended in, `first`: the end that
came first when the end move lost the actuator, else null), `actuator_left` (end mode, target,
last value written, set PV, read-back and held value as last seen, whether the read-back reached
the target, writes of the end move, notes), `limits` (definition, control limits of the set PV,
the ones used), `before` (set PV, read-back and held value before the scan), `pvs` (per PV: connected,
units, precision, control and display limits as the IOC reports them), warnings, planned points,
the estimate, the columns, the number of rows and every write (time, value, phase).

**definition.yaml**: the definition as it ran, overrides applied: `run` on it repeats the scan.

## 5. Every end

| How it ends | Exit code | Detected | The actuator | Rows |
|---|---|---|---|---|
| All points done | 0 | | to `end` in part steps | all |
| Definition or command line wrong | 2 | before connecting | not written | no files |
| Refused: actuator (set PV, read-back, held PV) or required detector not connected or INVALID, the held value more than the tolerance from the set PV's, a condition not holding, a point, the end value or the actuator's present value outside the limits (definition and DRVL/DRVH), limits that do not overlap | 3 | before the first write; every reason listed | not written | no files |
| A condition lost (false, INVALID, not connected) | 4 | within 50 ms | to `end` in part steps | the points done |
| The actuator lost: set PV, read-back or held PV not connected, set PV or held PV INVALID; the read-back INVALID for longer than `readback_lost_after`; any of these during the end move | 5 | within 50 ms (the read-back: after `readback_lost_after`) | **nothing written after it**, also when it reconnects: an IOC that restarted starts from its own values, and a write the program decided on before would act on a state it did not see | the points done |
| A required detector lost: not connected, or no valid value at a point | 6 | within 50 ms / after the point | to `end` in part steps | the points done (with the missing row) |
| A point not settled, `on_not_settled: end` | 7 | after `settle_timeout` | to `end` in part steps | including the `not_settled` row |
| An error in the program (an exception) | 8 | | to `end` in part steps, if it can still be written; the traceback in `scan.json` | the points done |
| ctrl-c (SIGINT) | 130 | within 50 ms | to `end` in part steps | the points done |
| SIGTERM | 143 | within 50 ms | to `end` in part steps | the points done |
| SIGKILL, power | (killed) | | where it was | the points done; `scan.json` says `running` |

The end move: from the last value written to the end target (`previous`, the number, or none for
`stay`) in part steps with `step_pause` between them; conditions are not checked during it (a lost
condition is usually the reason to go back). A write that fails (set PV disconnected) stops it,
and the note says where it stopped. The actuator lost during the end move (as in the table:
before each write, during each pause and while it waits for the read-back) stops it: nothing more
is written, the note names the last write, the exit code is 5, and `outcome.first` keeps the end
that started the move (T27; in the first round only the set PV INVALID after a pause was
checked, and the exit code stayed that of the first end). Then the program waits up to
`settle_timeout` for the read-back to reach the target and records whether it did. A second ctrl-c or SIGTERM during the
end move is logged and ignored; SIGKILL stops the program without the move.

## 6. Tests

| Test | What it shows |
|---|---|
| `python3 -m unittest discover -s scans/tests -t scans` (73 tests, under a second) | The point list (sign of the step, the end point, rounding near 0), part steps, unknown keys at every level, settling and its timeout (skip and end), nothing collected before the settle, settle time and dwell waited, the statistics with constructed sequences (held value, steps, bursts, invalid stretches, missing), invalid values left out, a missing point, a disconnect inside a dwell, each end with the actuator's writes checked (part steps, nothing after the actuator is lost, a failed write during the end move, a write the IOC did not confirm during the end move), the held PV (refusals: not known, not connected, different from the set PV; lost in the middle and in the end move), `readback_lost_after` (waited out when shorter, lost after it, in the end move, a shorter value), the alarm status in the reasons, every refusal with no write and no file, the rows on disk after an abort, `scan.json` "running" while the scan runs |
| `emulation/devtest/run.sh emulation/devtest/scan` (10 tests, about 2 min) | The program, started as `python -m mist2scan run`, against soft records (`scan.db`): a lagging read-back, three peaks with noise, a constant detector, a detector the test makes INVALID, a condition. The peaks found where the database puts them (fields E, F, G); read-back means within the tolerance; the constant detector `n` 1 at every point; missing values exactly at the points where the detector was INVALID; a condition lost, ctrl-c and SIGTERM: the actuator back in part steps (seen by a monitor of the test), the rows so far in the file; the IOC restarted: exit 5 and no write after it; a required detector not connected and a definition beyond the control limits: refused, nothing written; `check` writes nothing |

Each test of the device case was seen to fail once with the property it checks removed from the
program (the report of T23 lists how).

## 7. In the full emulation

`scans/config/emulation-extraction.yaml` steps the ion source supply (`AU-20P7-1:voltage:setpoint`,
read-back `AU-20P7-1:voltage:read`) from 1 to 15 kV and records the Faraday cup current
(`FC:current:get`, required), the supply's current and the discharge current (optional), with
the source supply on, the puller on and the cup in as conditions. In the plant model the cup
current is `beam_fraction * discharge * (1 - exp(-(V_source + V_puller) / 8000 V))`: a property
of the MODEL, not of MIST-2.

The source has to run first. Done by hand for T23 (with `flock /tmp/mist2emu.lock` held,
`make -C emulation up-plant`), by caput from the tools container, in this order:
`LOOP-DIS:mode:setpoint 0`, `TURBO1:start:set 1`, `VALVE:s1:set 1`, `VALVE:s2:set 1`,
`MFC:setSP 20`, wait for `TURBO1:atspeed:get` 1 (about 70 s), `TDK:voltage:setpoint 8`,
`TDK:current:setpoint 88`, `TDK:status:setpoint 1`, `REK-1:voltage:setpoint 150`,
`REK-1:SetToggleOutput 1`, `AU-20P7-1:voltage:setpoint 1000`, `AU-20P7-2:voltage:setpoint 2000`,
`AU-20P7-1:SetToggleOutput 1`, `AU-20P7-2:SetToggleOutput 1`, `VALVE:s4:set 1`. Then
`python -m mist2scan check` and `run` (scans/README.md, "In the emulation"); afterwards every
output off and the set points back to 0, `make -C emulation down`.

Run of 2026-11-24 (discharge current 17.43 A, puller 2 kV): 15 points, completed, exit code 0,
67 s (estimate of `check`: 51 s plus settling), the source supply back to 1000 V in 7 part steps
of 2 kV, the saved settings (`mist2emu-save`) unchanged.

| set (V) | read-back (V) | cup (mA) | source supply (mA) |
|---|---|---|---|
| 1000 | 1001.6 | 1.0894 | 1.093 |
| 3000 | 3001.0 | 1.6189 | 1.634 |
| 5000 | 5000.2 | 2.0314 | 2.056 |
| 7000 | 6997.9 | 2.3525 | 2.388 |
| 9000 | 9001.3 | 2.6027 | 2.648 |
| 11000 | 11000.0 | 2.7975 | 2.852 |
| 13000 | 13002.3 | 2.9492 | 3.013 |
| 15000 | 15000.9 | 3.0674 | 3.142 |

(Every second row of 15; the model gives 1.090 mA at 1 kV and 3.07 mA at 15 kV for 17.43 A.) The
cup current's record posted one to three values per 2 s dwell (`cup_n`): it holds its value
between changes, which section 2 counts.

## 8. The dipole scan in the emulation (T27)

The three parts of the dipole scan together: the shipped program runs the shipped definition
`scans/config/dipole.yaml` through ONE IOC (`dipole.db` with `libcom1_device.db` and
`first_contact.db`; `picoammeter.db` with its two `first_contact.db` loads) against the DAQ
service `daq/mist2daq` (sim backend) and the Keithley 6485 simulator. No IOC of the full
emulation loads these databases; the case is the only place where they run together.

```
emulation/devtest/run.sh emulation/devtest/dipolescan        # 11 tests, about 8 min
emulation/devtest/run.sh emulation/devtest/dipolescan -k test_4c    # one test alone
```

Every test sets its own preconditions (the fixture `ready`: the service running, the
picoammeter on, without a simulator fault, on autorange, zero check off, the set record not in
simulation mode, the magnet at 6 A and held there; test 1 makes its own power-on state), so each
passes alone with `-k` as well as in the order of the file.

The case's simulator side (`run_sim.sh`) runs three processes in one container: the service
(through the dipole case's `run_service.sh`, so a test stops and starts it with `build/daq-run`),
the picoammeter simulator (`sim.yaml`) and `coupling.py`. The coupling reads the magnet current
from the service's status port (the monitor channel `i1`, scaled as the service scales it) ten
times per second and sets the picoammeter simulator's input through its control port. Its model
(`coupling.yaml`): three Gaussian peaks on a background of 2 nA, at 10 A x sqrt(1, 2, 3) =
10.000, 14.142, 17.321 A of magnet current (three species of mass 1, 2, 3 at one energy), 150,
15 and 8 nA high, sigma 0.4 A; picoammeter noise 0.1 nA per reading (`sim.yaml`); monitor lag
0.5 s (`daq.yaml`). **None of these numbers is measured on MIST-2**: they are properties of the
case. The scan is started as the owner starts it, `python -m mist2scan run config/dipole.yaml`,
with `--start`, `--stop`, `--step`, `--dwell`, `--output` only (tests 3 to 6 use `--dwell 1` to
stay short). Test 3 uses a copy of the definition with one key changed (a question below), test
4a writes the set record in simulation mode to make it differ from the service; neither is a
second definition.

### Before a scan: what an operator must do

1. **Switch zero check off**: `caput pico1:zcheck:set 0` (OFF). After its power-on the 6485 has
   zero check on (PICOAMMETER.md), `pico1:current:get` is INVALID and both `check` and `run`
   refuse with "detector pico1 (pico1:current:get): INVALID (STATE)", writing nothing (test 1).
   Leave the range on AUTO (`pico1:range:set 0`) unless there is a reason: on a fixed range a
   peak above 105 % of it is INVALID (STATE), and with the shipped definition that ends the scan
   (test 3).
2. **Set the magnet once after every start of the DAQ service**: `caput dipole:current:set <A>`.
   After its start the service holds no value; the scan refuses with "actuator held PV
   dipole:current:held: INVALID (UDF): the value the device holds is not known" (tests 1 and
   4b), also when the set record still shows a value from before (it is processed only when
   written, DAQ.md section 3). This set is a step from an output the service does not know (the
   NI box may still be at its last value, or at 0 V): choose it near where the supply is
   believed to be.
3. `python -m mist2scan check config/dipole.yaml`, then `run`.

### What the case shows (tests of `test_dipolescan.py`)

| Test | Result |
|---|---|
| 1 after power-on | Refused by `check` and `run` (exit 3) with both reasons, "detector pico1 (pico1:current:get): INVALID (STATE)" and the held value not known (UDF); no file, no set at the service (status port: 0 commands `S`, 0 writes). With the magnet set once, only the picoammeter's reason remains; with zero check OFF through its PV, `check` exits 0 and shows "held 6.0 (dipole:current:held)" |
| 2 the spectrum | 7 to 19.5 A, step 0.5, the shipped dwell of 3 s, 26 points, exit 0, 178 s (`check`'s lower bound 136.5 s). Peaks (vertex of the parabola through the logarithms of three points) at 10.001, 14.141, 17.322 A against 10.000, 14.142, 17.321 A of the coupling; every read-back mean within 0.05 A; at the peak points measured minus model -0.07, -0.04, +0.07 nA, over all points at most 0.14 nA, rms 0.05 nA (noise 0.1 nA per reading). Magnet back to 6 A |
| R4 | dwell 1 s and 5 s, three points each (numbers below) |
| 3 overflow | Fixed 20 nA range, 8 to 16 A. Shipped (picoammeter `required: true`): exit 6 at 9.5 A, the first point on the mass-1 peak, row `missing`, reason "INVALID (STATE)"; magnet back in part steps. With `required: false`: exit 0, missing exactly at 9.5, 10, 10.5 A (model above 21 nA), all others within 0.5 nA of the model |
| 4a the set PV differs | The set record shows 7 A, the service holds 6 A: refused, "the set PV dipole:current:set shows 7, the device holds 6 (dipole:current:held): more than the tolerance 0.05 apart"; nothing sent |
| 4b service restarted, no scan running | The set record keeps 6 A and NO_ALARM, the service holds nothing: `check` and `run` refuse with the held value not known (UDF); the service received nothing |
| 4c the service stops in the middle | Stopped 0.3 s after the set of 10 A: "actuator lost" (exit 5) 0.10 s after the stop, detail "actuator held PV dipole:current:held INVALID (LINK): what the device holds is not known" (the IOC sees the closed connection at its next poll). Nothing written after it: every write in `scan.json` is before the stop, `writes_in_end_move` 0, a monitor on the set PV saw no value after the stop, and the service, started again, holds nothing and received no set. Then `check` refuses (held not known). In the first round, without the held PV, the same stop ended "not settled" after the 30 s settle timeout |
| 5 the picoammeter silent | Silenced in the settling of 10 A: the row of 10 A `missing`, reason "INVALID (TIMEOUT)", exit 6, the magnet back 10 to 6 A in four part steps (9, 8, 7, 6 seen by a monitor), the read-back reached 6 A, the service holds 6 A |
| 6 an IOC restart | Restarted in the settling of 10 A: exit 5, no write after it (`writes_in_end_move` 0, every write in `scan.json` before the restart); after the restart the set record took over 10 A from the service (first contact); the service, asked through its status port: no set received after the restart, held 10 A, monitor 10 A |

Each of tests 1 to 6 was seen to fail once with the property it checks removed (the reports of
T27 list how).

### The numbers of the three parts together (measured in the case)

The picoammeter is polled once per second (`picoammeter.db`, SCAN 1 s) and gives one new reading
per poll; a reading integrates NPLC 6 / 60 Hz = 0.1 s (0.3 s with autozero, PICOAMMETER.md
"Rate"). The scan's `n` counts the fresh read at the start of the dwell plus every update
during it (section 2).

| dwell | picoammeter values per point (`pico1_n`) | time per point (0.5 A steps) | 100 points (computed) |
|---|---|---|---|
| 1 s | 2 | 4.45 to 4.53 s | about 7.5 min |
| 3 s (shipped since T27) | 4 at every one of 26 points | 6.45 to 6.53 s | about 11 min |
| 5 s | 6 | 8.5 s | about 14 min |

Time per point = move (one write: 0.5 A < `max_step`) + settling (here about 1.5 s: the case's
lag of 0.5 s to within 0.05 A, and the 0.5 s poll of `dipole.db`) + `settle_time` 2 s + dwell.
`check` prints a lower bound without the settling: 136.5 s for the 26 points of test 2, which
took 178 s.

What it means:

- With a dwell of 1 s a point gets two values: the reading the fresh read finds, which was taken
  up to 1.3 s before the dwell began (poll period plus reading time), and the next one. About
  0.2 s of current is integrated per point. The shipped dwell is now 3 s: three new readings and
  the fresh read (still ASSUMED: whether that is enough on MIST-2 depends on the noise there).
  A dwell of N s gives N or N+1 values, so a whole number of poll periods.
- `settle_time` must cover the picoammeter's poll period plus a reading time (1.3 s) on top of the
  magnet's own settling, or the first value of a dwell is a reading from before the magnet got
  there. The shipped 2 s does; `scans/config/dipole.yaml` says so at the key.
- **Poll period of the picoammeter: keep 1 s** (`picoammeter.db` SCAN): the arithmetic gives a
  minimum of 0.46 s at NPLC 6 and 9600 baud, which leaves no room for the identity request and
  the instrument's response time, which is not known. **Integration time: keep NPLC 6** (the
  instrument's power-on value and its maximum at 60 Hz, Table 4-4); the database reads it and
  sets nothing. **`dipole.db` SCAN: keep 0.5 s**: it sets how fast settling is seen.

### Decided (owner, T27 second round) and open

- Built: the held PV (`actuator.held`, test 4), the read-back lost after `readback_lost_after`
  (unit tests), the alarm status in every INVALID reason, the dwell of 3 s.
- **Open, the owner's decision: an overflow ends the dipole scan** with the shipped `required:
  true`. On a fixed range a peak above the range is an ordinary event of a spectrum; `required:
  false` records it as missing and goes on (test 3), autorange avoids it. Left as shipped.

## 9. Not built

- Two-dimensional scans (one actuator per scan; a second axis would be a loop of scans).
- Scan state as PVs (running, point, progress) for the GUI and the logger: the scan is visible
  there only through the PVs it moves and reads.
- A GUI page to start or watch a scan.
- Analysis of the data: peak finding exists in the device case's test only.
- Detectors that are arrays (waveforms): only scalar values are used, others are "not a number".
- Control limits that change during the scan: they are read once at the start.
