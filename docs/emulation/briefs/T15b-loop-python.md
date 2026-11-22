Revised brief for task T15, 2026-11-22. It replaces `T15-loop-ioc.md` from "Goal" on. The parts "Setup", "Read first", "Background" and "Rules" of the original stay in force, with one correction: question 3 is answered, the loop runs at a set point of 22 A.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# What changed and why
The owner decided on 2026-11-22: **the PID runs in a Python service with pyepics, and the loop's own records are plain records in the platform IOC (`iocHV`).** No C code, no third IOC. His reasons: the loop acts on a time scale of about a second, so Python's timing is good enough; his group reads and changes Python, not C; and the later steps (gain scheduling, the neural network) are Python anyway.

The price of that choice is that the algorithm lives outside the IOC, in a process that can stop or misbehave. So the work is split in two layers:
- **The IOC records are the interface and the backstop.** They hold everything the operator sees and sets, and they enforce, without any help from Python: the output limits, the slew limit, that the actuator is written only in PID mode, and that the loop goes to MANUAL when the service stops.
- **The Python service is the algorithm and the judgement:** the PID, anti-windup, bumpless switching, and the decision to hand back.

# Goal
1. `EPICS/Db/loop.db`: a database template of plain records, loaded by `iocHV/st.cmd` once per loop. The discharge loop has the prefix `LOOP-DIS`, measures `REK-1:current:read` and acts on `TDK:current:setpoint`.
2. A Python service in a new top-level directory `loops/` (package `mist2loop`): started as `python -m mist2loop --config <file>`, standard library, PyYAML and pyepics only. It runs on the platform computer beside `iocHV`. In the emulation it is one more container of the Compose project, started and stopped with the rest.
3. A second loop later is one more `dbLoadRecords` line and one more entry in the service's configuration, without new code.

# Requirements
R1. **Algorithm** (Python). PID in parallel form: `u = Kp*e + I - Kd*d(pv_f)/dt`, `e = sp - pv`, `I += Ki*e*dt`. Derivative on the filtered measurement, not on the error. Fixed period; `dt` from the real time between two runs (monotonic clock), guarded against zero and against a long gap. The algorithm is a module without any EPICS import: state and inputs in, output and new state out, so that it is tested alone and can be used in a notebook.
R2. **Limits** (Python and IOC). Output minimum and maximum, and a slew limit in output units per second. The service applies them and its integrator does not grow while the output is held back by any of them in the direction of the error: say which anti-windup method you chose. The IOC enforces the same limits on what reaches the actuator, whatever the service writes: say how, with plain records.
R3. **Bumpless.** In MANUAL nothing of the loop writes the actuator, and the service follows the actuator's present set point. On MANUAL to PID the first output equals that set point. A change of a gain, a limit or the set point while in PID causes no jump of the output beyond what the proportional term and the slew limit allow.
R4. **Hand-back to MANUAL**, by itself, each with its reason shown as a word until the next request:
   a. a permit condition is not fulfilled. The conditions are macros of the load line (PV and required value), and the operator sees each one. For the discharge loop: `interlock_open` is 0, `REK-1:status:read` is 1 (output on, remote control), `TDK:status:get` is 1;
   b. a PV the loop uses is INVALID or not connected (measurement, actuator set point, a permit condition);
   c. its data is stale: the IOC stopped counting its heartbeat for longer than a time that is a setting;
   d. somebody else wrote the actuator set point while the loop was in PID (the operator has priority);
   e. the actuator did not accept a set (its set record ends INVALID);
   f. the service stopped or hangs: the IOC sees that the service's own counter stands still for longer than a time that is a setting, takes the mode back and raises an alarm. This one must work with the service killed;
   g. a start: after a start of the IOC, and after a start of the service, the mode is MANUAL, whatever was saved or was on before.
   After a hand-back the actuator keeps its last set point, and the mode request itself is back at MANUAL (latched, as the permit latch of the supplies in `rek.db`), so nothing returns to PID by itself.
R5. **Refusal.** A request for PID while a condition of R4 is not fulfilled, or while the service does not run, is refused, with the reason.
R6. **What the operator sees**, all as records of the loop: mode, reason of the last hand-back or refusal as a word, each permit condition, whether the service is alive, a flag while the output is at a limit, set point, measured value as the loop uses it, output, error, and the three terms for tuning.
R7. **Settings as records:** set point with its own limits, Kp, Ki, Kd, derivative filter time, output minimum, maximum and slew, the two times of R4 c and f. Saved by `iocHV`'s autosave as the current limit of the REK is (`limits.defaults`, `limits.sav`), except the mode. The default set point is 22 A (the owner's answer). The set point maximum defaults to 23 A, below the REK's full scale of 24 A: a free choice of ours, marked as to be confirmed. Default gains come from the plant model and are marked as assumed.
R8. **The service knows a loop by its prefix.** The names of the measurement, the actuator and the permit conditions are written once, in the load line of `loop.db`; the service works on the loop's own records. No name of the discharge loop in the Python code or in the template.
R9. **Rate.** Every write to the actuator is one more transaction on the TDK's serial line, which is also polled at 10 Hz. Choose the default period from that arithmetic and from the plant's time constant, do not write when the output changed by less than the actuator's resolution (a macro), and measure what the loop costs: read-back rate of the TDK with the loop in MANUAL and in PID.
R10. **PV names.** New names follow the lab's convention (`<PREFIX>:<quantity>:<setpoint|get|read>`, see decision D4 in DESIGN.md). Do not rename or change any existing PV. Do not add records for things that are not built: the neural-network step is not part of this task. Say in your design note where it would attach.
R11. **Existing databases.** Do not change `tdk.db`, `rek.db` or any other device database unless the loop cannot work otherwise. If you must, make the smallest change and name it in the report.
R12. **The service as a program.** It starts whether or not the IOC runs and connects when the IOC appears. It subscribes with monitors and does not poll. It logs one line per event (mode changes with reason, connection changes), not one per cycle. It ends cleanly on SIGTERM, with the loop in MANUAL. Give a systemd unit file for the real computer and say what must be installed there (Python version, pyepics version). The operating system of that computer is not known (assumption A22): mark the installation as not verified.

# What carries over from your work on the first brief
The behaviour you designed and tested (limits, slew, anti-windup, bumpless switching, hand-back reasons), ported to Python; the design note; the tests through PVs; the 22 A set point. Remove from your branch what the new design does not need: the C sources and their build lines, `iocBoot/iocLoop`, the `ioc-loop` service, the third IOC in the plan, the registry and the tests, and the same-host proof (a service that is only a Channel Access client has no such trap: say so in one sentence in the note). The branch that the lead merges must not contain leftovers of the first design. Its history may.

# Files you own
- `EPICS/Db/loop.db`, the load line and the defaults in `EPICS/ioc/iocBoot/iocHV/` (`st.cmd`, `limits.defaults`)
- `loops/` (new): package `mist2loop`, configuration, unit tests, systemd unit, `README.md`
- `emulation/compose.yaml` (the service, on the image `mist2-tools:dev`, which has pyepics), `emulation/Makefile`, `emulation/tools/ca-proof.sh` if it needs it
- `emulation/tests/` (new modules and what they need in the shared code)
- `plan/controls.yaml` (the loop as a device of a new class `loop` on `ioc_hv`, the roles of its records, the service; `software.components`, `software.loops` and WP10 brought to the owner's decision and to what is built; raise the revision), `plan/build.py`, `plan/registry.py`, `plan/test_build.py` where needed, the regenerated `RAS/mist2/ReactApp/src/registry/registry.json` and `plan/out/`
- `docs/emulation/LOOP.md` (new, your design and operating note), `emulation/README.md`, `emulation/tests/README.md`
Not yours: everything else under `RAS/` (the GUI gets its loop widget in the next task and shows an unknown class with a generic widget meanwhile), `docs/emulation/STATUS.md`, `PLAN.md`, `DESIGN.md`, `docs/emulation/README.md` (the lead keeps them: put what belongs there into your report).

# Deliverables
1. The database template, the service and the emulation service as above.
2. `docs/emulation/LOOP.md`: the two layers and what each guarantees, the algorithm in a few lines, the PV table, the hand-back rules with their time limits, the settings with defaults and where each default comes from, how to tune the loop on the real machine (which step to make, what to read from it, how the gains follow), how to install and start the service on the platform computer, where the neural-network step would attach, and what is not built.
3. Tests:
   A. **Algorithm alone**, without EPICS and without the emulation, by one command: each term, output limits, slew limit, anti-windup (after a long saturation the output leaves the limit without delay), bumpless start, a parameter change without a jump, `dt` guards.
   B. **System suite** (`make -C emulation test`, no plant): every record of the loop reads, every setting is written and read back, every reason of R4 a to f is provoked and seen within a limit you state and justify, R5, and R4 g for a restart of the IOC and for a restart of the service. For R4 f kill the service's container while the loop is in PID. **The backstop is tested without the service's help:** with the service stopped or replaced by a test client that writes wrong values, the actuator never receives a value outside the limits, never changes faster than the slew limit allows, and is never written in MANUAL. The suite ends with the loop in MANUAL. The generic tests that write every written PV of the registry must not switch a loop to PID by accident.
   C. **Closed loop on the plant** by one command of its own (for example `make -C emulation test-loop`; it starts the emulation with the plant and stops what it started): the source is brought to about 20 A of discharge current in MANUAL; MANUAL to PID is bumpless; a set point step to 22 A settles; a disturbance of the plant (its control port has an emission drift) is rejected; a set point the supply cannot reach ends at the output maximum with the flag, not in a runaway, and comes back; a hand-back in closed loop leaves the filament current where it was. Print a table: rise time, overshoot, settling time, steady-state error, writes per second to the TDK, read-back rates of TDK and REK in MANUAL and in PID. State your pass limits and where they come from.
4. `make -C emulation plan-check` passes, the registry is regenerated from the plan, and the whole system suite still passes and stays under 12 minutes.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    <your command for test A>
    flock /tmp/mist2emu.lock make -C emulation build
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock <your command for test C>
    flock /tmp/mist2emu.lock make -C emulation plan-check

All exit 0, and nothing is left running. The lead then switches the loop by hand from Channel Access on the emulation with the plant, pulls each hand-back once, kills the service in PID, and reads `LOOP.md` against what he sees.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t15-loop-ioc @ <commit>
    BUILT: one line per part
    ALGORITHM: in a few lines, with the anti-windup method
    BACKSTOP: what the IOC enforces without the service, and with which records
    PVS: name, type, meaning
    HAND-BACK: reason, who detects it (service or IOC), how, time limit
    SETTINGS: name, default, unit, source (owner, model, bus arithmetic, free choice)
    RESULTS: the table of test C, and the cost of the loop on the TDK's line
    VERIFIED: every acceptance command with exit code and key output, and how you saw new tests fail
    REMOVED: what of the first design you took out
    DECISIONS: choices the brief left open, each with one reason
    ASSUMED: everything that needs the owner's confirmation
    NEEDS THE LEAD: changes outside your files, text for STATUS.md, open questions
