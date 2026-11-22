You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T17: the data logger of work package WP9, a service that records the process variables of the machine in a time-series database with three retention tiers and an event log. A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t17`, on branch `emu/t17-logger`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo, and may pull images.
- **Shared machine.** Another engineer works on the GUI in another worktree at the same time and uses the same emulation. The emulation (fixed container names, network 172.30.0.0/24) can exist only once. Rule for both of you: take the lock for the whole time you have the emulation up, and bring down what you started before you release it. In practice one command: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`, or a `make` target that starts and stops by itself under `flock /tmp/mist2emu.lock`. Never leave the emulation running outside the lock, and never stop containers you did not start. If the lock is taken, wait: the other engineer's check takes up to 20 minutes. Your own containers (database, logger, Grafana) are a Compose project of their own and need the lock only while they talk to the emulation.
- Leave no container and no process running when you finish.

# Read first
1. `plan/controls.yaml`, section `software` (`intro`, `components`, `tiers`, `archiver`, `questions`) and work package WP9: what the owner wants. The store is decided: a time-series database (TimescaleDB on PostgreSQL) behind a small Channel Access logger of our own, with Grafana to look at the data.
2. `docs/emulation/README.md` and `docs/emulation/DESIGN.md` section 2: the emulation and its network. `docs/emulation/LOOP.md`: the discharge current loop, a Python service with its records in the platform IOC, and the pattern for a service beside the IOCs.
3. `plan/README.md`: how the plan, the databases and the `st.cmd` files are checked against each other, and how the device registry (`RAS/mist2/ReactApp/src/registry/registry.json`) is generated. The logger's list of PVs is generated the same way.
4. `emulation/tests/README.md` and `emulation/tests/system.py`: Channel Access with pyepics, simulator control, fault injection. `RAS/mist2/Makefile` and `RAS/mist2/env.template`: the pattern for a service with its own Compose project and an `.env` file that is not committed.
5. `docs/emulation/STATUS.md`, open points P31 (a client that read 200 PVs every 0.1 s disturbed the Matsusada monitors once: subscribe, do not poll) and P33 (clocks).

# Goal
A service that runs without any GUI, talks to the IOCs through Channel Access only, and records what the plan's tier table says:

| Tier | Content | Kept |
|---|---|---|
| 1 raw | every value as the IOC sends it (up to 10 Hz) | 30 days |
| 2 seconds | mean, minimum, maximum per second | 2 years |
| 3 minutes | mean, minimum, maximum per minute | for ever |
| events | set commands, alarms, interlock trips, loop hand-backs | for ever |

The same service runs against the emulation and against the real IOCs. Only its Channel Access settings and the place of its data differ.

# Requirements
R1. **Which PV in which tier comes from the plan.** Every existing PV in `plan/controls.yaml` gets a tier: the finest tier in which it is kept (a tier 1 PV is also in tiers 2 and 3; a tier 3 PV only in minutes), `events` for what is recorded on change only, or an explicit `none` with a reason. Use rules per role or record type with overrides per PV, so that the plan stays readable. A PV without a tier is a warning of `plan/build.py`, so that a PV added later cannot be forgotten. Propose the assignment as a table in your design note: the owner will review it. The tier definitions (resolution, life time) become machine-readable in the plan, and the logger's configuration is generated from it. A PV added to the plan is logged without a change in the logger.
R2. **Raw.** Every monitor update with the IOC's time stamp, value, alarm severity and status. Subscribe with monitors, never poll. Record when a PV disconnects and when it returns, so that a reader never holds a value across a gap. Enumerations keep their number and their state words, strings are stored as text.
R3. **Seconds and minutes.** Mean, minimum, maximum and the worst alarm severity per interval. A monitor sends a value only when it changes: a value that holds for an hour must read as that value for every second and minute of the hour, with the mean weighted by time, and an interval without a valid value must read as a gap. Decide where the reduction is computed (in the logger or in the database) by what gives these semantics with the least machinery, and say why.
R4. **Events.** One time-ordered log, kept for ever: every change of a written PV (set points, requests: old value, new value), every change of alarm severity of any PV (from, to, status), every change of the interlock permit and of each supply's output state, every change of a loop's mode with its reason, and the logger's own events (start, stop, database lost and back, samples dropped, clocks apart). Channel Access does not say who wrote a value: say so in the note, and do not invent a user.
R5. **Life times** are enforced by the database for each tier, and a test proves it with shortened life times.
R6. **Nothing lost silently.** While the database is down or slow the logger keeps a bounded buffer and writes it when the database returns. What does not fit is counted and logged as an event. A restart of the logger, of an IOC or of the database needs no manual step afterwards. Measure the load of the full emulation (rows per second, CPU, memory) and how long the buffer lasts.
R7. **Time.** Values carry the IOC's time stamp. A record that was never processed carries a time stamp of 1990: it must not be stored in 1990. A time stamp that is far from the logger's clock is stored under the logger's time, flagged, and logged as an event once per PV (P33).
R8. **The operator sees that logging is alive.** The logger writes its state once a second to records in the rack IOC (new database, prefix `LOGGER`, loaded by `iocRack/st.cmd`): a counter, the number of PVs connected and not connected, rows per second, database state, buffer fill. A record there turns to MAJOR alarm when the counter stops, so that the GUI's alarm display shows a dead logger without any new code. The logger does not log its own state records as raw data.
R9. **Reading.** A small Python module and a command line tool: one PV or several, a time range, a tier (or "best for this range"), as rows with gaps marked, to CSV. It hides how constant values and gaps are stored (R2, R3). This is what a notebook and the later neural-network training will use.
R10. **Looking.** Grafana with the data source and dashboards provisioned from files: one dashboard per page of the GUI, generated from the registry, with the same groups as the GUI's trend page, and a panel for the event log. No dashboard is edited by hand.
R11. **Deployment.** Its own Compose project in a new top-level directory `logger/` (database, logger, Grafana), with pinned image versions, data in named volumes, and settings in an `.env` created from a template (database password, Channel Access addresses, ports). Ports are bound to 127.0.0.1 unless a setting opens them; the GUI already uses 3000, 3001 and 9001. `make -C logger up`, `down`, `logs`, `test`. It starts whether or not the IOCs run and connects when they appear. Say which TimescaleDB features you use and under which licence each is.
R12. **Where it will run** on the real system is an open question of the owner (lab computer, rack computer, or a small server). Do not decide it: give in your note what it needs (CPU, memory, disk per day and per year for each tier, measured on the emulation and extrapolated, with the arithmetic shown), how to back it up and how to move it.

# Files you own
- `logger/` (new): the service, its image, Compose file, `env.template`, `Makefile`, tests, `README.md`
- `EPICS/Db/logger_status.db` (new) and its one load line in `EPICS/ioc/iocBoot/iocRack/st.cmd`
- `plan/controls.yaml` (tiers per PV, machine-readable tier definitions, the logger's status records, `software.archiver` and WP9 brought to what is built; raise the revision), `plan/build.py`, `plan/registry.py`, `plan/test_build.py`, a new generator if you want one, the regenerated registry and `plan/out/`
- `docs/emulation/LOGGER.md` (new, your design and operating note)
- `emulation/tests/` only where the new records of the rack IOC need it
Not yours: `RAS/` except the generated registry, `docs/emulation/STATUS.md`, `PLAN.md`, `DESIGN.md`, `docs/emulation/README.md` (the lead keeps them: put what belongs there into your report).

# Deliverables
1. The service as above, and `docs/emulation/LOGGER.md`: the data model (tables, what a row means), how constant values and gaps are stored and read, the tier table per PV group, life times, the status PVs, how to read data (three worked examples: a trend of one PV over an hour, the events of a day, the mean discharge current of a run), sizing, backup, what is not built.
2. Tests, by `make -C logger test` (it starts the emulation and the logger if needed and stops what it started):
   - every PV of the generated list is subscribed, and a value written to a set point appears in raw data and as an event with old and new value;
   - a 10 Hz PV: the number of raw rows over a minute equals the number of monitor updates a second Channel Access client counted in the same minute;
   - a constant PV and a changing PV: the seconds and minutes tiers hold the right mean, minimum and maximum against values computed independently from the raw data, including an interval across a change;
   - a silent simulator (fault injection) gives the alarm events and a gap, not a held value; an IOC stopped and started gives disconnect and return;
   - the database stopped for a minute and started: nothing lost, order kept; stopped for longer than the buffer: the loss is counted and logged;
   - life times with shortened values: old data of each tier disappears, the next tier keeps its own;
   - a never-processed record and a time stamp far off (R7);
   - the status records count, and the alarm rises within its limit when the logger is stopped;
   - the reading tool returns the same numbers as a direct query, and marks gaps;
   - Grafana answers and has one dashboard per GUI page.
   State each time limit and where it comes from.
3. `make -C emulation plan-check` passes, the registry is regenerated, and the whole system suite (`make -C emulation test`) still passes and stays under 13 minutes (it takes about 11.5 now). The suite fails a run that changes an IOC's saved settings (`limits.sav`, see the header of `emulation/tests/run.sh`): your tests leave them as they find them.
4. **The GUI is not yours, but it reads the registry.** It draws every device of the registry by its class and its check (`RAS/mist2/tools/gui-check.sh`) demands that every device record is shown. Model the logger's status records in the plan so that the GUI shows them without new code where that is possible (look at how the IOCs' own records and the existing classes are handled in `plan/README.md` and `RAS/mist2/ReactApp/src/registry/README.md`), on the Infrastructure page. The lead runs the GUI check after your branch and the GUI branch are merged. Say in your report what the GUI needs from its side, if anything.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock make -C logger test

All exit 0, and nothing is left running. The lead then starts the emulation with the plant and the logger, operates the source for some minutes, and reads the data back with your tool and in Grafana.

# Rules
- Do not invent facts about the machine. Life times and tiers are the plan's; what you choose beyond them is a setting with a comment and a line in the report.
- Do not rename or change any existing PV. No placeholder PVs, no dead code.
- Simple first: the logger is code the lab will maintain. Standard library, pyepics and one PostgreSQL driver; say why if you need more.
- Verify by running, not by reading. Show for each new test that it fails when the behaviour is broken, where that is cheap.
- The machine is shared with the GUI engineer's builds. A time limit that fails once and passes when you run it again alone is to be reported with both results, not cured by a wider limit.
- If a requirement turns out to be wrong or two of them collide, do the sensible thing, and say so in the report under DECISIONS.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t17-logger @ <commit>
    BUILT: one line per part
    DATA MODEL: tables and what a row means, in a few lines
    TIERS: PV groups with their tier and the reason
    RESULTS: load, buffer, sizes per day and per year
    VERIFIED: every acceptance command with exit code and key output, and how you saw new tests fail
    DECISIONS: choices the brief left open, each with one reason
    ASSUMED: everything that needs the owner's confirmation
    NEEDS THE LEAD: changes outside your files, text for STATUS.md, open questions
