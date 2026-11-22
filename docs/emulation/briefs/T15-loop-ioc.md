You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T15: the first control loop, a PID that holds the discharge current through the filament heating current, as a soft IOC of its own. A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch. Nobody else is working on the repository while you do.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t15`, on branch `emu/t15-loop-ioc`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. EPICS, the test tools and Python tooling live in containers (`docs/emulation/README.md`).
- The emulation uses fixed container names and the fixed network 172.30.0.0/24, so only one copy can run. Wrap every command that starts, uses or stops it in the lock: `flock /tmp/mist2emu.lock <command>`. You may rebuild the images (`make -C emulation build` from your worktree). Leave no container and no process running when you finish (`make -C emulation down`).

# Read first
1. `plan/controls.yaml`, section `software` (`loops`, `components`, `tiers`) and work package WP10: what the owner wants. Then the devices `fil_heat` (TDK, filament heating) and `fil_dis_old` (REK, filament discharge).
2. `docs/emulation/DESIGN.md` section 2 and `docs/emulation/README.md`: the emulation, how to start and test it, the plant model (section 6).
3. `python3 emulation/sim/tools/plant_step_response.py` and `emulation/sim/README.md` (plant section): the plant you tune against. Every number in it is a property of the model, none is measured on MIST-2.
4. `EPICS/Db/tdk.db`, `EPICS/Db/rek.db` (the permit latch `_permit:latch` is the pattern for a request that the IOC takes back), `EPICS/Db/ioc_info.db`, `EPICS/Db/interlockbox.db`, both `st.cmd` files, `EPICS/ioc/iocBoot/run-ioc.sh`, `EPICS/ioc/mist2App/src/Makefile`.
5. `emulation/tests/README.md`, `emulation/tests/system.py`, `conftest.py`: the system suite takes devices, PVs and IOCs from the registry. `plan/README.md`: how `plan/controls.yaml`, the databases and the `st.cmd` files are checked against each other and how the registry is generated.
6. `docs/emulation/STATUS.md`, "What the working point implies": at the owner's working point the REK delivers 24 A, its full scale. A loop around that point can only act downward. The owner has not yet said whether the loop will run below 24 A or wait for a larger supply (question 3). Build the loop so that this is a setting, and test it below 24 A.

# Background
MIST-2 is a filament-driven multicusp ion source. The TDK supply heats the filament (about 8 V, 90 A at the working point; set point PV `TDK:current:setpoint`). The REK supply holds the discharge voltage (150 V), and the discharge current it delivers (`REK-1:current:read`) follows the electron emission of the filament: steeply, with a thermal lag of about 1.4 s in the model. Both supplies hang on the HV platform IOC (`iocHV`) and are polled at 10 Hz. The interlock permit (`interlock_open`) lives on the rack IOC. Operators change set points from a web GUI at any time.

# Goal
A soft IOC `iocLoop` that runs next to `iocHV` on the HV platform computer and talks to the other IOCs through Channel Access only. It holds one loop today and takes a second one by one more `dbLoadRecords` line. In the emulation it is a third IOC container. Whatever runs in the emulation must run on the real computer unchanged.

# Requirements
R1. **Algorithm.** PID in parallel form: `u = Kp*e + I - Kd*d(pv_f)/dt`, `e = sp - pv`, `I += Ki*e*dt`. Derivative on the filtered measurement, not on the error. Fixed period from the record scan; `dt` from the real time between two runs, guarded against zero and against a long gap.
R2. **Limits.** Output minimum and maximum, and a slew limit in output units per second, all applied to what is written to the actuator. Anti-windup: the integrator does not grow while the output is held back by any of the three in the direction of the error. Say which method you chose.
R3. **Bumpless.** In MANUAL the loop never writes the actuator and follows its present set point. On MANUAL to PID the first output equals that set point. A change of a gain, a limit or the set point while in PID causes no jump of the output beyond what the proportional term and the slew limit allow.
R4. **Hand-back to MANUAL**, by itself, each with its reason shown until the next request:
   a. a permit condition is not fulfilled. The conditions are macros of the load line (PV and required value). For the discharge loop: `interlock_open` is 0, `REK-1:status:read` is 1 (output on, remote control), `TDK:status:get` is 1;
   b. a PV the loop uses is INVALID or not connected (measurement, actuator set point, a permit condition);
   c. its data is stale: the IOC that owns the measurement stopped counting its heartbeat, for longer than a time that is a setting;
   d. somebody else wrote the actuator set point while the loop was in PID (the operator has priority);
   e. the actuator did not accept a set (its set record ends INVALID);
   f. the loop IOC starts: always MANUAL, whatever was saved.
   After a hand-back the actuator keeps its last set point, and the mode request itself is back at MANUAL (latched, as the permit latch of the supplies), so nothing returns to PID by itself.
R5. **Refusal.** A request for PID while a condition of R4 is not fulfilled is refused, with the reason.
R6. **What the operator sees.** Mode, reason of the last hand-back or refusal as words, a flag while the output is at a limit, set point, measured value as the loop uses it, output, error, and the three terms for tuning.
R7. **Settings as PVs:** set point with its own limits, Kp, Ki, Kd, derivative filter time, output minimum, maximum and slew, stale time. Saved by autosave as the current limits of the supplies are (`limits.defaults`, `limits.sav`), except the mode. Default gains come from the plant model and are marked as assumed. The set point maximum defaults to a value below the REK's full scale, with a comment that says why.
R8. **Template.** No name of the discharge loop in the C code or in the database template: PV names, conditions, units, limits, period and prefix are macros.
R9. **Rate.** Every write to the actuator is one more transaction on the TDK's serial line, which is also polled at 10 Hz. Choose the default period from that arithmetic and from the plant's time constant, do not write when the output changed by less than the actuator's resolution (a macro), and measure what the loop costs: read-back rate of the TDK with the loop in MANUAL and in PID.
R10. **PV names.** New names follow the lab's convention (`<PREFIX>:<quantity>:<setpoint|get|read>`, upper-case device prefix, see decision D4 in DESIGN.md). The discharge loop has the prefix `LOOP-DIS`. Do not rename or change any existing PV. Do not add PVs for things that are not built: the neural-network step of the plan is not part of this task. Say in your design note where it would attach.
R11. **Existing databases.** Do not change `tdk.db`, `rek.db` or any other device database unless the loop cannot work otherwise. If you must, make the smallest change and name it in the report.

# The IOC
- Same EPICS application and image as the other IOCs (`EPICS/ioc`, binary `mist2`): C code goes into `EPICS/ioc/mist2App/src`. Keep the algorithm in a file of plain C without any EPICS include, so that it can be tested on its own, and the record glue in a second file.
- `EPICS/ioc/iocBoot/iocLoop/` with `st.cmd`, the IOC's own records (`ioc_info.db`, prefix `IOC-LOOP`), autosave. It starts without error whether or not the other IOCs run, and connects when they appear.
- Emulation: service `ioc-loop`, address `.13`, health check as the other IOCs. `make -C emulation up`, `down`, `restart`, `logs`, `ca-proof` cover it.
- On the real platform computer two IOCs share one host. Channel Access has a known trap there (a unicast name search reaches only one of them). Describe in your design note how the two IOCs and their clients must be configured, and mark it as not verified.

# Files you own
- `EPICS/ioc/mist2App/src/` (new files, `Makefile`), `EPICS/Db/loop*.db`, `EPICS/ioc/iocBoot/iocLoop/`, `EPICS/ioc/iocBoot/run-ioc.sh`
- `emulation/compose.yaml`, `emulation/Makefile`, `emulation/tools/ca-proof.sh`, `emulation/docker/` if the image needs it
- `emulation/tests/` (new modules, and what the third IOC needs in the shared code), a unit test of the algorithm where you see fit
- `plan/controls.yaml` (the loop IOC as a host, the loop as a device of a new class `loop`, the roles of its records, `software.loops` and WP10 brought to what is built; raise the revision), `plan/build.py`, `plan/registry.py`, `plan/test_build.py` where the third IOC needs it, and the regenerated `RAS/mist2/ReactApp/src/registry/registry.json` and `plan/out/`
- `docs/emulation/LOOP.md` (new, your design and operating note), `emulation/README.md`, `emulation/tests/README.md`
Not yours: everything else under `RAS/` (the GUI gets its loop widget in the next task; it shows an unknown class with a generic widget meanwhile), `docs/emulation/STATUS.md`, `PLAN.md`, `DESIGN.md`, `docs/emulation/README.md` (the lead keeps them: put what belongs there into your report).

# Deliverables
1. The loop, the IOC and the emulation service as above.
2. `docs/emulation/LOOP.md`: the algorithm in a few lines, the PV table, the hand-back rules with their time limits, the settings with defaults and where each default comes from, how to tune it on the real machine (which step to make, what to read from it, how the gains follow), the two-IOCs-on-one-host note, and what is not built.
3. Tests:
   A. **Algorithm alone**, without EPICS and without the emulation, by one command: each term, output limits, slew limit, anti-windup (after a long saturation the output leaves the limit without delay), bumpless start, a parameter change without a jump, `dt` guards.
   B. **System suite** (`make -C emulation test`, no plant): the loop IOC starts without error, every PV reads, every setting is written and read back, every reason of R4 a to e is provoked and seen within a limit you state and justify, R5, R4 f across a restart of the loop IOC, and `docker stop` / `docker start` of the `ioc-hv` container: hand-back, the loop IOC keeps running and reconnects. The suite ends with the loop in MANUAL. The generic tests that write every written PV of the registry must not switch a loop to PID by accident.
   C. **Closed loop on the plant** by one command of its own (for example `make -C emulation test-loop`; it starts the emulation with the plant and stops what it started): the source is brought to about 18 A of discharge current; MANUAL to PID is bumpless; a set point step to 20 A settles; a disturbance of the plant (its control port has an emission drift) is rejected; a set point the supply cannot reach ends at the output maximum with the flag, not in a runaway, and comes back; the hand-back in closed loop leaves the filament current where it was. Print a table: rise time, overshoot, settling time, steady-state error, writes per second to the TDK, read-back rates of TDK and REK in MANUAL and in PID. State your pass limits and where they come from.
4. `make -C emulation plan-check` passes, the registry is regenerated from the plan, and the whole system suite still passes and stays under 12 minutes.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    <your command for test A>
    flock /tmp/mist2emu.lock make -C emulation build
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock <your command for test C>
    flock /tmp/mist2emu.lock make -C emulation plan-check

All exit 0, and nothing is left running. The lead then switches the loop by hand from Channel Access on the emulation with the plant, pulls each hand-back once, and reads `LOOP.md` against what he sees.

# Rules
- Do not invent facts about the machine. Gains, limits and times that come from the model or from your judgement are settings with a comment that says so, and a line in the report.
- Simple first: a physicist must be able to read the algorithm file in ten minutes.
- No placeholder PVs, no dead code, no commented-out alternatives.
- Verify by running, not by reading. A test that cannot fail proves nothing: show for each new test that it fails when the behaviour is broken, where that is cheap.
- If a requirement turns out to be wrong or two of them collide, do the sensible thing, and say so in the report under DECISIONS.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t15-loop-ioc @ <commit>
    BUILT: one line per part
    ALGORITHM: in a few lines, with the anti-windup method
    PVS: name, type, meaning
    HAND-BACK: reason, how detected, time limit
    SETTINGS: name, default, unit, source (model, bus arithmetic, free choice)
    RESULTS: the table of test C, and the cost of the loop on the TDK's line
    VERIFIED: every acceptance command with exit code and key output, and how you saw new tests fail
    DECISIONS: choices the brief left open, each with one reason
    ASSUMED: everything that needs the owner's confirmation
    NEEDS THE LEAD: changes outside your files, text for STATUS.md, open questions
