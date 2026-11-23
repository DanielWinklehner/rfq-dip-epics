You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T19: the first contact of the Matsusada and REK high-voltage supplies after an IOC start must not have a gap in which an operator's write is accepted and not sent (open point P40). A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t19`, on branch `emu/t19-supply-first-contact`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- In a new worktree the GUI's sources are missing until you run `git submodule update --init` there (needed before `make -C RAS/mist2 dev-up`).
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo.
- **Shared machine.** The lead uses the same emulation from another checkout. The emulation (fixed container names, network 172.30.0.0/24, one volume `mist2emu-save` with the IOCs' saved settings) can exist only once. Take the lock for the whole time you have the emulation up, and bring down what you started before you release it: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`, or a `make` target that starts and stops by itself under `flock /tmp/mist2emu.lock`. Never leave the emulation running outside the lock, and never stop containers you did not start. If the lock is taken, wait.
- Leave the saved settings as you found them: a limit or set point you change by hand is written back before you bring the emulation down (the suite prints at its start what differs from `limits.defaults`).
- Long commands (the suite takes about 12.5 minutes, the GUI check about 10) may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Leave no container and no process running when you finish.

# Read first
1. `docs/emulation/STATUS.md`: open point P40 (this task), P29 and the closed P20 (what the supplies do in their first seconds, wanted and to be kept), P28, and the block "Request records after an IOC start" under "Done".
2. `EPICS/Db/first_contact.db` with its header, and `docs/emulation/briefs/T18-first-contact.md`: the same fault was found and removed there. The pattern that holds: one check and records chained by output links with PP and by forward links, which EPICS processes inside the caller's lock.
3. `EPICS/Db/matsusada_au20p7.db` and `EPICS/Db/rek.db`: sections "first contact" (`_init:probe`, `output:init`, `_init:vtake`, `_init:vcopy`, `_limit:apply`) and the output gate (`SetToggleOutput`, `OutputIntlk`, `_out:switch`, `ToggleOutput`, `_permit:read`, `_permit:latch`). The two files have the same records.
4. `emulation/tests/README.md`, `emulation/tests/system.py`, `emulation/tests/test_11_first_contact.py` (the structure test and the test that writes through an IOC restart), the tests that cover the supplies' start (search for the gate and GRACE), and the device case `emulation/devtest/matsusada`.
5. `plan/README.md`: every record is in `plan/controls.yaml`, every PV has a logging tier.

# The fault
In the base of our image (EPICS 7.0.10, `/opt/epics/base/modules/database/src/std/rec/seqRecord.c`) a `seq` record runs every link group as a callback of its own, also with a delay of 0 (`processNextLink`: "Always use the callback task to avoid recursion"), and `processCallback` takes and releases the record's lock for each one. A client's write can come between any two steps.

1. `voltage:setpoint` starts in simulation mode (`SIMM YES` in the database), so that nothing is sent before the supply's own setting is known. At the first valid echo `_init:vtake` starts the seq `_init:vcopy`: step 1 copies the echo into the set point (processed, in simulation mode), step 2 sets `SIMM` to NO. A voltage that an operator writes between the two steps is accepted without alarm, not sent, and not replaced afterwards: the set point shows a voltage the supply does not have. Lowering is the bad direction: the field shows 0 V and the supply stays at 15 kV.
2. `output:init` (a seq) sets `ToggleOutput.SIMM` to YES, copies the probed state into `ToggleOutput`, sets `SIMM` to NO, copies the state into `SetToggleOutput` and into the gate's previous value, and five seconds later enables the gate. Whatever processes `ToggleOutput` between the first three steps is not sent. The gate is held then, so in normal use nothing does; but the order of all these steps against a client's write to `SetToggleOutput` is not fixed either.

# Requirements
R1. **No gap.** For both supplies' databases: the check that starts a take-over and every step that switches simulation mode or copies a value into a record a client can write run under ONE hold of the lock set. Argue it from the source of the base for every record you use, as `first_contact.db` does, and name the lines.
R2. **Behaviour kept.** What an operator and the other records see stays as it is, except that the gap is gone:
   - before the first valid answer nothing is sent, the voltage set point takes the supply's setting at the first valid echo, and a voltage written before that is replaced by the supply's setting (P20);
   - the output request and `ToggleOutput` take the supply's state at the first contact, nothing is sent for it, the gate starts `GRACE` seconds later and its first evaluation sends nothing if the permit is there (P29);
   - the current limit is sent after the first contact as today;
   - a supply that answers late, or is power-cycled, behaves as today.
   No PV is renamed or changes its type. If you find that a kept behaviour is itself a fault, do not change it: report it.
R3. **It cannot get stuck.** No path leaves `voltage:setpoint` or `ToggleOutput` in simulation mode after the supply has answered. Test `SIMM` in every case you test.
R4. **Every seq of the databases.** List every `seq` record in `EPICS/Db` (`output:init`, `_init:vcopy`, `_out:switch` in both supplies' files, `_drop` in `loop.db`, any other) with what its steps do and whether a write or an event between two steps can do harm. `_out:switch` is the switching sequence behind the interlock gate: say from the records what happens when the permit is lost while a switch-on sequence runs. Change a seq that is not part of the first contact only if you can show the fault with a test first; otherwise report.
R5. **One pattern.** Reuse or widen `first_contact.db` if the supplies' case fits it without bending it; otherwise a second small file beside it, with the same structure and a header that says how it works and why nothing is sent. Internal records start with `_`.
R6. **The plan stays the truth.** New and removed records in `plan/controls.yaml` (internal ones with tier `none`), `python plan/build.py` without warnings. Do not raise the plan's revision. Regenerated files (`registry.json`, `plan/out/`) as a commit of their own at the end.

# Tests
- The structure test of `test_11_first_contact.py` widened to the supplies: no record of a take-over is of a type that defers its work, no delay field is set on the steps, the links are the chain you describe.
- For one Matsusada supply on the rack IOC and for the REK on the platform IOC: a client writes `voltage:setpoint` in a tight loop while the IOC restarts. Afterwards, with the writing stopped: `SIMM` is NO, and the set point equals the supply's echo and the simulator's own value. This is the invariant the old records can break and the new ones cannot. Every write the IOC confirmed after the take-over was received by the simulator or left the record in alarm.
- The existing tests of the supplies' start, of the gate and of the interlock latch pass unchanged. If one of them asserted the old record structure, say which and why you changed it.
- **Time.** The suite takes 12 min 20 s to 12 min 46 s today and my budget for it is 13 minutes. Do not add an IOC restart to the default run: ride on the restarts that are there (`test_11_first_contact.py` restarts the rack IOC once, `test_09_loop.py` the platform IOC once), and mark what needs more as `slow` with the command to run it. Report the suite's time from a run with nothing else on the machine.

# Files you own
- `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`, `EPICS/Db/first_contact.db` or a new file beside it, and the supplies' load lines in the two `st.cmd` files if a new file is loaded per supply
- `emulation/tests/` (new tests; existing ones only where they assumed the old structure), `emulation/devtest/matsusada` if it names changed records
- `plan/controls.yaml` (records only), the regenerated registry and `plan/out/`
Not yours: `RAS/` except the generated registry, `logger/`, `loops/`, `EPICS/Db/loop.db` (report what you find in its `_drop`), the valve, pump and gauge databases, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `DESIGN.md`.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock emulation/devtest/run.sh emulation/devtest/matsusada
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
All exit 0, the suite with the saved settings unchanged and under 13 minutes. The lead then restarts each IOC by hand with a supply's output on and a voltage set, and looks at set point, echo, output state and what the simulator received.

# Rules
- Do not invent facts. A claim about how EPICS processes a record comes with the file and line of the base in our image.
- No change of behaviour beyond this task.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (step by step with the source lines, and why it cannot get stuck), TABLE (R4: every seq), VERIFIED (commands, exit codes, times, and how each new test was seen to fail), DECISIONS, ASSUMED, NEEDS THE LEAD (text for STATUS.md, anything of the plan the lead must do).
