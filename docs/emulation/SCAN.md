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
a stop signal, the set PV and the read-back connected, the set PV not INVALID (the IOC did not
confirm the write), every required detector connected, every condition holding (connected, not
INVALID, the comparison true). The first that fails ends the scan (section 5). A point
interrupted in this way has no row.

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
`n` is 0, and the reason says why ("INVALID", "not connected", "no answer"). An older value is
never carried into a point.

## 3. The definition, key by key

YAML. A key that is not listed here is an error, at every level (a misspelt `tolerence` must not
become a default). All numbers in the PV's own units (EGU of the set PV).

| Key | Required | Meaning |
|---|---|---|
| `name` | no | Name of the scan; the directory is `<name>-<date>-<time>` |
| `description` | no | Text, copied into `scan.json` |
| `actuator.set` | yes | The set PV: the only PV the program writes |
| `actuator.readback` | yes | The read-back PV, compared with the point |
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
detectors, conditions, end, units and the estimated time (moves, settle times and dwells; at
most, every point to its settle timeout), and says whether the scan would start. It writes
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
`outcome` (`code`, `reason`, `detail`, the `point` and `phase` it ended in), `actuator_left`
(end mode, target, last value written, set PV and read-back as last seen, whether the read-back
reached the target, writes of the end move, notes), `limits` (definition, control limits of the
set PV, the ones used), `before` (set PV and read-back before the scan), `pvs` (per PV: connected,
units, precision, control and display limits as the IOC reports them), warnings, planned points,
the estimate, the columns, the number of rows and every write (time, value, phase).

**definition.yaml**: the definition as it ran, overrides applied: `run` on it repeats the scan.

## 5. Every end

| How it ends | Exit code | Detected | The actuator | Rows |
|---|---|---|---|---|
| All points done | 0 | | to `end` in part steps | all |
| Definition or command line wrong | 2 | before connecting | not written | no files |
| Refused: actuator or required detector not connected or INVALID, a condition not holding, a point, the end value or the actuator's present value outside the limits (definition and DRVL/DRVH), limits that do not overlap | 3 | before the first write; every reason listed | not written | no files |
| A condition lost (false, INVALID, not connected) | 4 | within 50 ms | to `end` in part steps | the points done |
| The actuator lost: set PV or read-back not connected, set PV INVALID | 5 | within 50 ms | **nothing written after it**, also when it reconnects: an IOC that restarted starts from its own values, and a write the program decided on before would act on a state it did not see | the points done |
| A required detector lost: not connected, or no valid value at a point | 6 | within 50 ms / after the point | to `end` in part steps | the points done (with the missing row) |
| A point not settled, `on_not_settled: end` | 7 | after `settle_timeout` | to `end` in part steps | including the `not_settled` row |
| An error in the program (an exception) | 8 | | to `end` in part steps, if it can still be written; the traceback in `scan.json` | the points done |
| ctrl-c (SIGINT) | 130 | within 50 ms | to `end` in part steps | the points done |
| SIGTERM | 143 | within 50 ms | to `end` in part steps | the points done |
| SIGKILL, power | (killed) | | where it was | the points done; `scan.json` says `running` |

The end move: from the last value written to the end target (`previous`, the number, or none for
`stay`) in part steps with `step_pause` between them; conditions are not checked during it (a lost
condition is usually the reason to go back). A write that fails (set PV disconnected) stops it,
and the note says where it stopped. Then the program waits up to `settle_timeout` for the
read-back to reach the target and records whether it did. A second ctrl-c or SIGTERM during the
end move is logged and ignored; SIGKILL stops the program without the move.

## 6. Tests

| Test | What it shows |
|---|---|
| `python3 -m unittest discover -s scans/tests -t scans` (57 tests, under a second) | The point list (sign of the step, the end point, rounding near 0), part steps, unknown keys at every level, settling and its timeout (skip and end), nothing collected before the settle, settle time and dwell waited, the statistics with constructed sequences (held value, steps, bursts, invalid stretches, missing), invalid values left out, a missing point, a disconnect inside a dwell, each end with the actuator's writes checked (part steps, nothing after the actuator is lost, a failed write during the end move), every refusal with no write and no file, the rows on disk after an abort, `scan.json` "running" while the scan runs |
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

## 8. Not built

- Two-dimensional scans (one actuator per scan; a second axis would be a loop of scans).
- Scan state as PVs (running, point, progress) for the GUI and the logger: the scan is visible
  there only through the PVs it moves and reads.
- A GUI page to start or watch a scan.
- Analysis of the data: peak finding exists in the device case's test only.
- Detectors that are arrays (waveforms): only scalar values are used, others are "not a number".
- Control limits that change during the scan: they are read once at the start.
