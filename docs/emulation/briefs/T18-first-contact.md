You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T18: after an IOC start, the request records of the valves, the turbopumps and the ion gauge take over the state of their device at the first contact, instead of standing undefined until an operator writes them. A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t18`, on branch `emu/t18-first-contact`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo.
- **Shared machine, four users of one emulation**: the lead, the GUI engineer, the logger engineer, and you, each in a checkout of their own. The emulation (fixed container names, network 172.30.0.0/24, one volume `mist2emu-save` with the IOCs' saved settings) can exist only once. Take the lock for the whole time you have the emulation up, and bring down what you started before you release it: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`, or a `make` target that starts and stops by itself under `flock /tmp/mist2emu.lock`. Never leave the emulation running outside the lock, and never stop containers you did not start. If the lock is taken, wait: a run of another engineer takes up to 20 minutes, and several may be queued.
- Leave the saved settings as you found them: a set point or setting you change by hand in the emulation is written back before you bring it down (the suite prints at its start what differs from `limits.defaults`).
- Leave no container and no process running when you finish.

# Read first
1. `docs/emulation/STATUS.md`, open points P25 (this task), P10 and P29 (related behaviour of the supplies, not yours to change).
2. `EPICS/Db/matsusada_au20p7.db`, sections "first contact" (`_init:probe`, `output:init`, `_init:vtake`, `_init:vcopy`): the pattern that exists. A request record is processed once in simulation mode (`SIMM`), so that it takes a value and loses its undefined state without anything being sent to the device.
3. `EPICS/Db/solenoidbox.db`, `EPICS/Db/turbo_pump.db`, `EPICS/Db/turbo.db`, `EPICS/Db/aim.db` with `aim.proto` and `libcom1.proto`, and their load lines in `EPICS/ioc/iocBoot/iocRack/st.cmd`.
4. `emulation/tests/README.md`, `emulation/tests/system.py` (Channel Access, simulator control, fault injection, container requests) and `emulation/tests/test_09_loop.py`, `test_10_lost_permit.py` as examples of tests that restart an IOC.
5. `plan/README.md`: the plan, the databases and the `st.cmd` files are checked against each other; every PV has a logging tier (`plan/controls.yaml`, section `logging`).

# The problem
A record that was never processed since the IOC started has status UDF and severity INVALID. The request records below are written only by an operator, so after every start of the rack IOC they read 0 with INVALID until somebody presses a button, while the device keeps the state it had:

    VALVE:s1:set ... VALVE:s8:set    (s1 to s4 bo, s5 to s8 ao, solenoidbox.db)
    TURBO1:start:set, TURBO2:start:set    (turbo_pump.db)
    AIM:enable    (aim.db)

Since the GUI sets values in place, the request buttons of these devices stand on the Overview, and after an IOC start they are all drawn in the INVALID colour and show "closed" or "stop" for a valve that is open and a pump that runs. `RAS/mist2/tools/gui-check.sh` prints the records in a line that starts with `note: INVALID (UDF) through Channel Access`.

Writing an initial value at the start (PINI on the output record) is not an option: it would close the foreline valve and stop the turbopump at every IOC start.

# Requirements
R1. **Take over at the first contact.** After a start of the rack IOC, as soon as the device has answered for the first time, each request record above shows the state the device is in, with severity NO_ALARM. Nothing is sent to the device for this: prove it with the simulator (no set command between the IOC's start and the first write of a client), and prove that the device's state is the same before and after the IOC's restart.
R2. **No contact, no value.** While the device has not answered since the IOC's start, the request stays INVALID: its state is not known, and that is the truth. When the device answers later, the request takes over then.
R3. **Once per IOC start.** After the take-over the records behave exactly as today: a write of a client sends the acknowledged set, a command the device rejects or does not answer puts the record into alarm, and the read-back never overwrites the request again. A client's write that comes before the take-over wins: it is sent as today, and the take-over does not happen after it.
R4. **It cannot get stuck.** If you use simulation mode, no path may leave a request record in simulation mode, where a client's write would be accepted and silently not sent. Show how the design excludes it (for example one record that runs to its end), and test that `SIMM` is NO after the take-over, after a start without contact, and after a contact that comes late.
R5. **The ion gauge.** `AIM:enable` has no read-back record today. The gauge reports "cold cathode on" as bit 1 of the status word in every reply to the pressure request (`aim.proto`). If the take-over needs a new record for it, add it as a proposed PV in the plan with the other records of the gauge. If the state cannot be read without changing how the pressure is read, do not guess: leave `AIM:enable` as it is and say what would be needed.
R6. **Every request record of the registry.** Start each IOC freshly and list every written record of `registry.json` that is INVALID with status UDF before anything is written: a table in your report with the record, what it is, and what you did (taken over, or left with the reason). Records of the list above are the task; a record you find beside them is reported, and fixed only if the same pattern fits without new facts. Internal records that nobody operates (`LOOP-DIS:_drop`, `AU:alloff:fanout`) stay.
R7. **One pattern, not eight copies.** The records of the take-over are loaded per request from one small database file with macros, or are a block that the existing files repeat by substitution. Internal records start with `_` after the device prefix, as in the Matsusada database. No existing PV is renamed and none changes its type.
R8. **The plan stays the truth.** New records are in `plan/controls.yaml` (internal ones with tier `none`), `python plan/build.py` runs without warnings. Do not raise the plan's revision (the lead does at the merge), and commit the regenerated files (`registry.json`, `plan/out/`) as a commit of their own at the end, so that the lead can redo it.

# Files you own
- `EPICS/Db/solenoidbox.db`, `EPICS/Db/turbo_pump.db`, `EPICS/Db/aim.db`, `EPICS/Db/aim.proto`, a new database file for the take-over, and the load lines of these devices in `EPICS/ioc/iocBoot/iocRack/st.cmd`
- `emulation/tests/`: a new test file, and existing tests only where they assumed the old behaviour
- `plan/controls.yaml` (new records only), the regenerated registry and `plan/out/`
- the simulators under `emulation/` only if a test needs to count commands and cannot today
Not yours: `RAS/` except the generated registry, `logger/`, `loops/`, `EPICS/Db/loop.db`, the supplies' databases, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `DESIGN.md` (the lead keeps them: put what belongs there into your report).

# Deliverables
1. The databases as above, each with a header comment that says how the take-over works and why nothing is sent.
2. Tests in the system suite (`emulation/tests/`), each seen failing once without the fix:
   - with the foreline valve open, the vent valve closed, a turbopump running and the ion gauge on: the rack IOC restarts; afterwards every request shows the device's state with NO_ALARM, the devices are in the same state as before, and the simulators received no set command;
   - a device silent at the IOC's start (fault injection): its requests stay INVALID; the fault cleared: they take over;
   - after the take-over a write works and is acknowledged, a rejected or unanswered set alarms as today, and a later change of the read-back does not change the request;
   - a write before the take-over is sent and stays;
   - `SIMM` of every request is NO in each of these cases.
   The suite takes 11.6 to 12.2 minutes today and must stay under 13: share one IOC restart between as many checks as you can.
3. `gui-check.sh` passes, and its `note: INVALID (UDF)` line no longer names a request record.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
All three exit 0; the suite reports the saved settings unchanged and stays under 13 minutes.

# Rules
- Do not invent facts. If a protocol detail is not in the repository's files, say so and leave that part.
- No change of behaviour beyond this task: what a client's write does, what an alarm means, and every PV name stay as they are.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (the take-over, step by step, and why it cannot get stuck), TABLE (R6), VERIFIED (commands, exit codes, times, and how each new test was seen to fail), DECISIONS, ASSUMED, NEEDS THE LEAD (text for STATUS.md, anything of the GUI or the plan the lead must do).
