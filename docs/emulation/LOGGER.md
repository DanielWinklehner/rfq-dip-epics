# Data logger: design and operation

Work package WP9 (`plan/controls.yaml`). The store is decided: a time-series database
(TimescaleDB on PostgreSQL) behind a small Channel Access logger of our own, with Grafana to look
at the data. The logger is `logger/mist2log` (Python, pyepics, psycopg); its own Compose project
in `logger/` (`make -C logger up`, `logger/README.md`). It runs without any GUI and talks to the
IOCs through Channel Access only. The same service runs against the emulation and against the
real IOCs: only `EPICS_CA_ADDR_LIST` and the place of its data (the Docker volume) differ.

Every number marked *measured* comes from the emulation (no plant model), not from MIST-2.

## 1. What is logged, and where it comes from

| Tier | Content | Kept | Table |
|---|---|---|---|
| 1 raw | every monitor update as the IOC sends it (up to 10 Hz) | 30 days | `raw` |
| 2 seconds | mean, minimum, maximum, worst severity per second | 2 years | `seconds` |
| 3 minutes | mean, minimum, maximum, worst severity per minute | for ever | `minutes` |
| events | PVs stored on change only, and the event log | for ever | `changes`, `events` |

The tiers and their life times are the plan's (`software.tiers`, now with `id`, `interval` and
`keep_days`). Which PV goes into which tier is in the section `logging` of `plan/controls.yaml`:
rules per PV, per widget class, for internal records, per role, for written PVs and per record
type, the first that applies wins, each with a reason. A tier is the finest one a PV is kept in:
a raw PV is also in seconds and minutes, a seconds PV also in minutes. `plan/build.py` gives every
existing PV a tier and warns about a PV without one (and about a rule with an unknown tier or one
that names a PV or class that does not exist); the Word document lists the rules with the number
of PVs each covers. `plan/registry.py` writes the tier of each PV (`log`) and the tiers
(`logging.tiers`) into the registry, which the logger reads at its start: a PV added to the plan
is logged after `make -C emulation registry` and `make -C logger restart`, without a change in
the logger.

### Proposed assignment (for the owner's review)

| PV group | Rule | Tier | PVs | Why |
|---|---|---|---|---|
| Supply voltages and currents read (AU, REK, TDK), pressures, temperatures, flows, Faraday cup current, turbopump speed and current, the loop's measured value, output, error and terms | type `ai` | raw | 42 | measured values: fault finding, loop tuning, training data |
| The NT 20's last RS-232 record (text) | role `raw` | raw | 2 | kept to find the record format (P14) |
| Supply power | role `power` | seconds | 6 | computed from voltage and current, both kept raw |
| Cold-junction temperatures of the thermocouple board | role `junction` | minutes | 4 | board temperature: long-term only |
| `PRESSURE:diag_box:getpressure` | PV | minutes | 1 | measures nothing in phase 1 (its gauge goes to the second cross in phase 2) |
| Every written PV: set points, current limits, output requests, valves, pumps, gauge, MFC, loop settings and mode request, ALL HV OFF | written | events | 45 | each change is a set command in the event log |
| Set point echoes (`vget`, `ilimit_get`, MFC `sp`) | roles | events | 11 | an echo changes only after a set |
| States: output states, Matsusada status, TDK mode and fault, doors, valves, turbo relays and state, loop mode, reason, permits, limit flag, service alive, the interlock permit `interlock_open` | roles `state`, `open`, `service`; types `bi`, `mbbi`, `longin` | events | 46 | states change rarely; every change is an event |
| Identity texts (device name, firmware, channel list), IOC mode | types `stringin`, `lsi` | events | 23 | change at a firmware update or a restart |
| IOC heartbeats, NT 20 record age | roles `heartbeat`, `age` | none | 4 | count every second; a stopped IOC shows as the disconnect of all its PVs, a stale NT 20 record as INVALID speed and current |
| The logger's own state `LOGGER:*` | class `logger` | none | 8 | R8: its loss is seen in the rack IOC |
| Internal records (fan-outs, sequences, mirrors, arrays) | internal | none | 142 | what they do shows in the public PVs |

Totals (registry of plan revision 0.13): 180 PVs logged (44 raw, 6 seconds, 5 minutes, 125
events), 154 not.

## 2. Data model

| Table | A row means | Key, size |
|---|---|---|
| `pv` | one logged PV: name, tier, kind (number, enum, text), record type, unit, state words, device, role; whether it is connected now, the last severity and (events PVs) the last value written to the event log | `id` |
| `raw` | one monitor update of a raw PV: the IOC's time stamp, value (the number of an enumeration), text (its state word, or the string), severity, status, flags. **severity NULL: a gap**, no value from this time on | hypertable, chunks of 1 day |
| `changes` | the same for an events PV (on change only, kept for ever) | hypertable, chunks of 30 days |
| `seconds`, `minutes` | one interval in which something happened: start, mean, minimum, maximum over the time with a valid value, `valid` (share of the interval with a valid value), worst severity, and the state at its end (`last`, `last_severity`) | `(pv, t)`, hypertables, chunks of 30 / 365 days |
| `events` | the event log: time, PV, kind, old, new, value, severity, status, detail | plain table |
| `state` | one row: the logger's start, its last write, and how far raw, seconds and minutes are complete | |
| `tier` | the plan's tiers and life times | |

**Flags** of a raw or changes row: 1 the IOC's time stamp was far from the logger's clock, 2 the
record was never processed (time stamp of 1990), 4 the first value after a gap stored at the time
the logger saw it (its time stamp lay before the gap), 8 a gap written by the logger (it did not
run, or rows were lost), not by a disconnect.

**Valid** means: connected, severity below INVALID, a number. A value with INVALID severity is
stored in `raw` as the IOC sent it, and is a gap for every reader and interval.

**How constant values and gaps are stored.** Monitors send a value only when it changes. So
`raw` and `changes` hold one row per change, and the seconds and minutes tables hold one row only
for an interval in which the PV changed (or a gap began or ended). An interval without a row
continues the state at the end of the row before it: a value that holds for an hour is one raw
row and one seconds row, and reads as that value for every second and minute of the hour. A gap
is a row too (raw: severity NULL; intervals: `last` NULL), so a reader never carries a value
across it. The logger writes gap rows for every PV where its knowledge ends: at a disconnect,
when it starts again after not running (from the end of what it wrote last, `state`), and after
rows that did not fit into its buffer. Beyond the `state` times nothing is known yet: readers see
a gap there.

**Where the reduction is computed: in the logger.** The semantics need, for each interval, the
value held from before it and the time each value held. The logger has exactly this in memory
(`core.Interval`, 40 lines): it closes an interval 2 s after its end (late updates), with the
mean weighted by time over the valid part. In the database the same would need window functions
over the previous row, a job that runs again for rows written late (after a database outage) and,
for time weighting, the TimescaleDB Toolkit; continuous aggregates cannot see the value held from
the interval before. The price: an interval open when the logger is killed is lost (its raw rows
remain for 30 days).

## 3. Events

One time-ordered log (`events`, view `event_log` with PV names), kept for ever:

| kind | When | old, new, detail |
|---|---|---|
| `set` | a written PV changed (set point, limit, request, setting) | old and new value (an enumeration as word and number) |
| `state` | another events PV changed: interlock permit, output states, doors, valves, pumps, loop mode | old, new; a loop's mode carries the reason that belongs to this change of mode in `detail` (`LOOP-DIS:reason:get: interlock open (1)`) |
| `alarm` | the alarm severity of any logged PV changed | old and new severity, `detail` the status (COMM, LINK, UDF, HIHI ...) |
| `connection` | a PV disconnected (`lost`) or returned (`back`) while the logger runs | |
| `logger` | start (with how far the data was complete), stop, database lost, database back, rows lost (count in `value`), clocks apart (once per PV) | |

**A loop's mode and its reason.** The loop's records are written in the order request, mode,
reason (a hand-back and a refusal alike), so the reason of a hand-back arrives after the change
of mode. The mode event waits for it: it is written with the reason that comes next, or, when
none comes within 0.5 s (`core.CONTEXT_WAIT`: the reason did not change, as at a request for
PID), with the reason in effect then. The event keeps the time of the mode change. The reason's
own change is an event of its own as well.

**What a loop writes while it is in PID is not a set command.** A loop in PID writes its actuator
(`TDK:current:setpoint` for `LOOP-DIS`) up to five times a second. The plan says which PV a loop
writes and when: `databases: loop.db: drives: {macro: ACT, while: {role: mode, value: 1}}`, written
into the registry as `drives` of the loop's device; a second loop is one more load of `loop.db`
and needs nothing in the logger. While the loop's mode is PID, the actuator is a signal: every
write is a row of `raw` and goes into the seconds and minutes tiers, and there is no `set` event
and no `changes` row. The loop's mode events mark the border. Outside PID a write to it is a set
command like any other. A reader finds:

| Time | `raw` | `seconds`, `minutes` | `changes`, `events` |
|---|---|---|---|
| MANUAL | nothing | nothing (gap) | every write: a row and a `set` event |
| at the change to PID | the value then (flag 16) | intervals begin | the mode event of the loop |
| PID | every write | mean, minimum, maximum | nothing of the actuator (its alarms are still events) |
| at the change to MANUAL | a gap (flag 16) | a gap | the value then (flag 16), the mode event with its reason |

`log_read` of the actuator in tier `events` (and `best`, and Grafana) reads both tables and gives
the whole series without a gap at either border; tiers `raw`, `seconds` and `minutes` give the
times in PID and gaps between them. The column `pv.driven_by` names the loop's mode PV.

**Channel Access does not say who wrote a value.** A `set` event is a change of the record's
value, whoever made it: the GUI, a script, the loop service, autosave at an IOC start. The log
names no user and does not guess one. An events PV that changed while the logger did not run is
logged at its first value after the start (old: the last value in the log).

## 4. Time

Rows carry the IOC's time stamp, with three exceptions (`core.Recorder._time`), each flagged:

- a time stamp before 2000 is that of a record never processed (EPICS epoch 1990): stored under
  the logger's time, flag 2. Not an event (every set record that was never written has one);
- a time stamp more than `MIST2LOG_CLOCK_SKEW_S` (10 s, our choice) from the logger's clock is
  stored under the logger's time, flag 1, and logged once per PV and run ("clocks apart"). The
  first value after a connection is exempt in the past direction: it may come from a record
  processed long ago;
- a value stamped before the PV's last gap (a passive record that did not change while it was
  disconnected or while the logger did not run) is stored when the logger sees it, flag 4, so that
  the gap stays a gap.

Clocks apart (open point P33) are not cured here: NTP on every computer.

## 5. Nothing lost silently

The main thread hands one batch per second to a writer thread through a buffer of at most
`MIST2LOG_BUFFER_ROWS` rows (2 000 000 by default). Each batch is written in one transaction
with the `state` row. While the database is lost or slow the batches wait, in their order; the
writer tries again every second. A batch that does not fit is not kept: its rows are counted
(`LOGGER:dropped:get`, MINOR from the first). When the buffer has been written, the logger writes
a gap for every PV from the end of what was written, the event "rows lost" with the count and
the time span, and the present state of every connected PV (flag 4). A restart of the logger, of
an IOC or of the database needs no manual step: the logger waits for the database at its start,
Channel Access reconnects by itself (measured: an IOC container restarted, all its PVs back
within 12 s), the writer reconnects by itself. (The logger needs the database at its start to
register its PVs; until it is there it waits and logs nothing.)

**A batch the database refuses** (a data or integrity error: the database answered, and will
answer the same again) is given up at once: its rows are counted as lost (`LOGGER:dropped:get`),
the writer goes on with the next batch, and the logger writes a gap for every PV from the end of
what was written before it, the event "rows lost" with the count and the database's message, and
the present state of every PV. Only a lost connection keeps a batch for another try.

## 6. The logger's state in the rack IOC

`EPICS/Db/logger_status.db`, prefix `LOGGER`, loaded by `iocRack/st.cmd`, written by the logger
once a second (Channel Access puts). The logger does not log these records.

| PV | Meaning | Alarm |
|---|---|---|
| `LOGGER:count:get` | +1 per second | |
| `LOGGER:alive:get` | 1 while the count changed within 5 s (macro TIMEOUT), else 0 | MAJOR at 0, also from the IOC start until a logger writes |
| `LOGGER:connected:get`, `disconnected:get` | logged PVs connected / not connected | MINOR while one is not connected |
| `LOGGER:rows:get` | rows written per second (mean of 10 s) | |
| `LOGGER:db:get` | unknown, connected, lost | MAJOR when lost |
| `LOGGER:buffer:get` | share of the buffer in use, % | MINOR from 50 %, MAJOR from 90 % |
| `LOGGER:dropped:get` | rows lost since the logger started | MINOR from 1 |

They are the device `logger` (class `logger`, subsystem `services`) of the registry. The GUI
shows them without new code: on the Infrastructure page in the device table with their worst
alarm, in the device window (generic widget), and as a tag on the Diagnostics page and the
Overview. A dead logger is MAJOR there.

## 7. Reading

The database functions do the work, so that Grafana, the Python module and SQL give the same
answer: `log_read(pv, from, to, tier)` (tier `raw`, `events`, `seconds`, `minutes` or `best`) and
`log_trend(pvs[], from, to, step_ms)` for Grafana. Each row has `kind`: `value` (a stored row),
`held` (the value in effect, repeated where needed), `gap` (no valid value). "best" is the finest
tier the PV is kept in whose life time covers the start and that gives at most 20 000 rows (raw
counted at 10 rows per second): raw up to 33 minutes, seconds up to 5.5 hours, minutes beyond.
The module `mist2log.read` (`Reader.read`, `Reader.events`) and its command line tool wrap them.
The read-only role `mist2log_reader` is used.

**A trend of one PV over an hour.**

    make -C logger read ARGS="TDK:current:read --from 2026-11-22T14:00 --to 2026-11-22T15:00 --tier seconds" > tdk.csv

3600 rows `t, value, min, max, text, severity, valid, kind, tier`; in Python:

    from mist2log.read import Reader
    with Reader(port=5434, password="...") as r:
        rows = r.read("TDK:current:read", "2026-11-22T14:00", "2026-11-22T15:00", tier="seconds")

**The events of a day.**

    make -C logger read ARGS="--events --from 2026-11-22T00:00 --to 2026-11-23T00:00"

or `SELECT * FROM event_log WHERE t >= '2026-11-22' AND t < '2026-11-23' ORDER BY t`.

**The mean discharge current of a run** (from 14:05 to 16:40), weighted by the time with a valid
value, from the seconds tier:

    SELECT sum(value * valid) / sum(valid) AS mean_A, sum(valid) AS seconds_valid
      FROM log_read('REK-1:current:read', '2026-11-22 14:05', '2026-11-22 16:40', 'seconds');

(or the same over `minutes` for a run older than two years). The run's start and end can be
taken from the event log, for example the `state` events of `LOOP-DIS:mode:get` or of
`REK-1:read_output_status`.

## 8. Looking: Grafana

Data source and dashboards are provisioned from files (`logger/grafana/provisioning`), Grafana
cannot change them. `mist2log/dashboards.py` writes them from the registry at every
`make -C logger up` (and `restart`): one dashboard per page of the GUI (Overview, the subsystem
pages, Trends, Infrastructure), each subsystem page with the GUI's trend groups (the read-backs
of its devices, one graph per role and unit, pressures on a log scale) and the event log of its
devices; Trends with any logged PV picked; Infrastructure with the PVs not connected and the
whole event log. The graphs are those the registry lists under `trends` (the plan's
`trends`, shared with the GUI): `roles`, and `beside`, a set point drawn in the graph of its
read-back. So the plasma generator's page has the loop's measured value with its set point in one
graph and its output in another, as in the GUI.

The tier follows the range as `best` does (section 7): raw up to 33 minutes, seconds up to 5.5
hours, minutes beyond; seconds and minutes are merged to the panel's interval. The data source
sets Grafana's smallest interval to 1 s (`timeInterval`; Grafana's default for SQL sources is one
minute, which drew every window in minutes until 2026-11-22). The newest point is at most the
logger's tick and write behind (raw, about 2 s; seconds 3 s).

## 9. Deployment

`logger/compose.yaml`: `timescale/timescaledb:2.17.2-pg16`, `grafana/grafana-oss:11.3.0`, the
logger image `mist2log:1` (from `python:3.12.16-slim`, pyepics 3.5.7, psycopg 3.2.3, pinned in
`logger/requirements.txt`). Data in the named volumes `mist2log-data` and `mist2log-grafana`.
Settings in `logger/.env` from `env.template`. Ports bound to 127.0.0.1 (5434 database, 3300
Grafana) unless `MIST2LOG_BIND` opens them. The logger runs on the host network (Channel Access
as any client of that computer) and starts whether or not the IOCs run. Restart policy
`unless-stopped`.

**TimescaleDB features used and their licences:** hypertables and `time_bucket` (Apache 2.0);
retention policies and the job scheduler that runs them (Timescale Licence, TSL "community":
free to use, not to offer as a database service). Not used: compression, continuous aggregates,
the Toolkit. Without the TSL features, the life times would need a `drop_chunks` call (Apache 2.0)
from the logger instead.

## 10. Sizing, backup, moving (R12)

**Measured** on the emulation (no plant model, nobody operating, 2026-11-22, 10 minutes after a
warm-up of 3 minutes, WSL2 on a 28-thread desktop): 180 PVs, of which 44 raw.

| Table | Rows per second | Bytes per row on disk (indexes included) |
|---|---|---|
| `raw` | 102.7 | 156 |
| `seconds` | 36.2 | 141 |
| `minutes` | 0.73 | 193 (few rows yet: pages not full) |
| `changes`, `events` | 0 while nobody operates; 3.7 and 0.6 during the test suite (faults injected without pause) | 136, 200 |

CPU: logger 1.5 % of one core, database 0.6 %. Memory: logger 39 MB (plus at most about 300 MB
for a full buffer: 152 bytes per buffered row, measured with tracemalloc), database 556 MB
(the TimescaleDB image tunes PostgreSQL to the computer's memory at the first start).

**Arithmetic** (per day = rows per second x 86 400 x bytes per row):

| Tier | Per day | Kept | Steady size |
|---|---|---|---|
| raw | 102.7 x 86 400 = 8.87 M rows x 156 B = 1.38 GB | 30 days | 41 GB |
| seconds | 36.2 x 86 400 = 3.13 M rows x 141 B = 0.44 GB | 730 days | 322 GB (161 GB per year) |
| minutes | 0.73 x 86 400 = 63 000 rows x 193 B = 12 MB | for ever | 4.4 GB per year |
| changes + events | 0 at rest; 4.3 rows/s x 86 400 x 170 B = 63 MB in a day of continuous faults | for ever | below 1 GB per year in normal operation (an estimate, not measured) |

**A day in PID** adds, for each loop, its actuator as a signal: at most one write per period
(0.2 s), 5 rows per second; in the lead's session on the plant model 63 writes in 78 s, 0.8 per
second. Raw: 0.8 to 5 x 86 400 = 69 000 to 432 000 rows x 156 B = 11 to 67 MB a day, kept 30
days (0.3 to 2 GB); seconds: at most one row per second, 86 400 x 141 B = 12 MB a day (9 GB in two
years); minutes: 1440 rows, 0.3 MB a day. Nothing of it goes into the tables kept for ever except
the minutes and the two mode events of each switch (before this round, 0.8 to 5 set events and
as many rows of `changes` per second, 70 000 to 430 000 a day each, for ever).

So about 370 GB after two years, then about 5 GB more per year. The seconds tier dominates: in
the emulation every analog value carries noise and changes in every second; on the machine an
ADC's noise does the same, so this is probably realistic. Choices if that is too much (none
needed for a 1 TB disk): TimescaleDB compression of chunks older than a few days (Timescale
Licence, typically a tenth of the size), a deadband (MDEL) on noisy records, or a shorter life
time for seconds of some groups. CPU and memory are no constraint: any of the three candidate
computers carries it. **The buffer** of 2 000 000 rows lasts 2 000 000 / 139.6 rows per second =
14 300 s, about 4 hours without database; memory then about 300 MB. Raise `MIST2LOG_BUFFER_ROWS`
for longer outages (about 150 MB per 1 000 000 rows).

**What the computer needs:** Linux with Docker (or PostgreSQL 16 with TimescaleDB 2.17 and Python
3.12 natively), a network path to both IOCs for Channel Access (the logger is a client like the
GUI), 1 GB of memory for database and logger, 1 TB of disk for two years with headroom, NTP.

**Backup.** `docker exec mist2log-db-1 pg_dump -U mist2log -Fc mist2log > mist2log-$(date +%F).dump`
(a consistent copy while the logger runs). The tables `events`, `changes`, `minutes` (for ever) are
the ones that cannot be had again; `raw` and `seconds` expire anyway. A nightly dump of
`events changes minutes pv tier state` (`pg_dump -t ...`) is small. Restore: `pg_restore` into a
new database with the extension (`timescaledb-pre_restore()` / `timescaledb_post_restore()`, as
TimescaleDB's documentation describes for its dumps).

**Moving it to another computer.** Stop the logger (`docker compose stop logger`: the stop is
logged), dump, copy `logger/.env`, restore on the new computer, `make -C logger up` there. The
time it did not run is a gap. Or move the volume `mist2log-data` with the database stopped.

## 11. Tests (`make -C logger test`)

`logger/tests/test_core.py` tests the rules alone (16 tests, under a second).
`logger/tests/test_system.py` runs against the emulation, in this order:

| Test | Proves | Time limit and its source |
|---|---|---|
| every PV subscribed | the database's PV list is the registry's (tiers too), every PV connected, `LOGGER:connected:get` = 180, `disconnected:get` = 0, the logger's own records not in the list | 30 s: the logger's start; CA connects in under a second, the state records are written every second |
| set point | `MFC:setSP` written: its change row and a `set` event with old and new value | 3 s: one tick (1 s) and the write |
| a loop in PID | the loop of the registry's `drives` brought to PID (supplies on, actuator inside the output limits), 4 s of writes, a door opened: no `set` event and no `changes` row of the actuator in PID, every write a raw row (equal to a second client's count, to the microsecond), a seconds row in every second of PID, a `set` event again after the hand-back, the reader's series without a gap; the mode event PID to MANUAL carries "interlock open", the reason that came after it | 30 s for the service and the supplies; 10 s for the permits (output states polled every 1 s); 1 s to PID and 1 s for the hand-back (LOOP.md section 4) |
| 10 Hz PV | raw rows of `TDK:current:read` over a minute = the monitor updates a second client counted, time stamps equal to the microsecond | the minute, then close delay 2 s and the write |
| changing PV | every second and the minute of that minute: mean, minimum, maximum against values computed from the raw rows (value held from before each interval, weighted by time) | |
| constant PV | a raw PV that holds reads as its value in every second and minute, and has no interval rows meanwhile | 180 s to find one that held 125 s (the logger may have just started) |
| silent simulator | the thermocouple board silent: INVALID, alarm events (INVALID, then NO_ALARM), seconds and raw read as gaps, not as the held value | 5 s to INVALID, 20 s to recover (emulation/tests/README.md) |
| reading tool | the CLI's raw rows equal a direct query, the held value at both ends; the seconds equal the table; the silent window comes back as gaps without values | |
| IOC stopped and started | `iocHV` stopped: a `connection lost` event and a raw gap row per PV; started: `back` for every PV | 5 s + write: the TCP connection closes with the container; 60 s: container start and CA reconnect |
| never processed | no row before 2000 anywhere; a record still unprocessed after the IOC start has its row under the logger's time, flag 2 | |
| state records | the counter counts; the logger stopped: `alive:get` 0 MAJOR, not before 3.5 s; started again: alive, all connected, a stop and a start event, a gap row per raw PV | 7 s: TIMEOUT 5 s, scan 1 s, last count up to 1 s before the stop; 30 s for the start |
| database stopped 60 s | `db:get` lost, then connected; raw rows over the outage = a second client's count; events "database lost", "database back"; nothing dropped | 8 s to notice (one tick, connect timeout 5 s); 60 s to recover |
| database stopped longer than the buffer | with a buffer of 3000 rows and 45 s without database: `dropped:get` > 0 (MINOR), one event "rows lost" with the same count, a logger gap row, then a resumed row; the reader shows a gap in between | as above |
| life times | the production policies are 30 and 730 days; in a scratch database with life times shortened to 1 h (raw) and 2 h (seconds) and chunks of 10 min, rows 10 min, 90 min and 3 h old: raw keeps the newest, seconds two, changes, minutes and events all | |
| refused batch | in a scratch database, a batch with a status no smallint holds between two good ones: both good ones written within 5 s, the bad one counted as lost with the database's message, a gap and one "rows lost" event | 5 s: three transactions |
| Grafana | health OK; one dashboard per GUI page with the page's title; the plasma generator's page has the loop's measured value with its set point and its output; asked through its query API as a viewer, with the interval its front end would use (the data source's minimum), a 2-minute window of the busiest raw PV gives every raw row at its own time, up to the newest; the panels' queries of one page return data as the read-only user | 40 s: Grafana rereads the files every 30 s; 90 s for a minute of data; 3 s: one tick and the write |
| load | rows per second, rows per tier, bytes per row, CPU and memory (`logger/build/load.md`) | |

**How the tests were seen to fail.** Each rule of `core.py` was broken on purpose and the unit
tests run again: mean not weighted by time (3 failed), 1990 time stamps stored as they come (1),
far-off time stamps kept (1), every interval stored instead of only the changed ones (1), a value
from before a gap stored at its old time (1), INVALID values counted as valid (1), the buffer
without limit (1). The system tests failed on real faults while they were written: the read
functions held a value at the start of a range that began exactly on a gap row (fixed), the
reading tool printed the stale value of an INVALID row in a gap (fixed), and a condition that
waited for an exactly empty buffer never held while data flows.

**Fix round T17b, seen to fail with the old code:** the loop's actuator treated as an events PV
again (driver ignored): the unit test of the actuator fails (and the system test's "no set event
in PID"); the mode event written at once: 3 unit tests fail, without the wait for the reason 2;
the old `log_trend` (tier by the panel's interval) and the data source without `timeInterval`:
the Grafana test gets 0 of 323 raw rows; `dashboards.py` without `beside`: the Grafana test finds
no graph of measured value and set point; the writer treating a refused batch as a lost database:
"not within 5 s: the writer goes on after the refused batch".

## 12. Not built

- Who wrote a value (Channel Access does not tell).
- Compression (TSL) of old chunks: not needed for the sizes above; it would cut raw and seconds
  to a fraction.
- A widget for the class `logger` in the GUI (the generic one shows it).
- A reload of the PV list without a restart.
- Installation on the real computer (where is open), backups as a timer, NTP.
- Measured numbers of the real machine.
