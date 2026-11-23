You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T21: a switching command that is written into the switching record of a Matsusada or REK high-voltage supply while that record is busy must not be lost (open point P47). A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t21`, on branch `emu/t21-switch-resend`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- In a new worktree the GUI's sources are missing until you run `git submodule update --init` there (needed before `make -C RAS/mist2 dev-up`).
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo.
- **Shared machine.** The emulation (fixed container names, network 172.30.0.0/24, one volume `mist2emu-save` with the IOCs' saved settings) can exist only once. Take the lock for the whole time you have the emulation or a device case up, and bring down what you started before you release it: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`, or a `make` target that starts and stops by itself under `flock /tmp/mist2emu.lock`. Never leave anything running outside the lock, and never stop containers you did not start. If the lock is taken, wait.
- Leave the saved settings as you found them (the suite prints at its start what differs from `limits.defaults`).
- Long commands (the suite takes about 12.7 minutes, the GUI check about 10, the device case 7.5) may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t21 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- After a GUI check: `git checkout -- RAS/mist2/tools/screenshots` (it rewrites screenshots).
- Leave no container and no process running when you finish.

# Read first
1. `docs/emulation/STATUS.md`: open point P47 (this task), the block "The output permit as a state" under "Done" (task T20, the rule `_permit:enforce`, and the fault its first version had), P28, P45 in the list of closed points.
2. `EPICS/Db/matsusada_au20p7.db` with its header, section "output": `SetToggleOutput`, `OutputIntlk` (the gate), `_out:switch`, `_out:limit`, `_out:remote`, `_permit:latch`, `_permit:enforce` with its comment, `ToggleOutput`, `read_output_status`. `EPICS/Db/rek.db` has the same records with other defaults; the two files are kept in step. `EPICS/Db/supply_first_contact.db` with its header (the take-over puts `ToggleOutput` into simulation mode for three steps under one hold of the lock).
3. `EPICS/Db/matsusada_co_ctrl.proto` (and `rek.proto`): `toggle_output`.
4. The device case `emulation/devtest/matsusada`: `ioc.cmd`, `permit.db`, `mat.py`, `test_matsusada.py`, `test_permit_enforce.py` (its asyn trace of what the IOC writes to the line, its 120 permit losses, how it holds a simulator signal), `sim.yaml`. The simulator: `emulation/sim/mist2sim/devices/matsusada_co.py` and the fault modes of `emulation/sim/mist2sim/core/simulator.py` (`silent`, `slow` with `ms`).
5. `emulation/tests/test_11_first_contact.py` (the structure tests of the take-over), `emulation/tests/README.md`.
6. `plan/README.md`: every record is in `plan/controls.yaml`.

# The fault
`ToggleOutput` (a `bo` with StreamDevice) sends RST, SW0 or SW1, reads the SW setting back and compares it; that takes some tens of milliseconds. A value written into it while it is busy is stored in `VAL` and not sent, unless EPICS marks the record to run again, which it does only when the writer carries the put flag (`dbDbLink.c`, `processTarget`: a client's write and a change event give it, a periodic scan does not). The gate `OutputIntlk` is also evaluated by its own 1-second scan. So an operator's off that follows an on within the switching time, and that the gate's scan sees before the change event arrives, is stored and not sent: the supply stays on with its request off, `ToggleOutput` shows 0 with an INVALID alarm (its compare failed), and the gate does not try again. The mirror case leaves the supply off with the request on. T20 covers the case "permit lost" by a rule on the supply's state (`_permit:enforce`); with the permit present nothing covers it.

Read by me in the base of our image (`docker run --rm --entrypoint sh mist2-ioc:dev -c '...'`, base under `/opt/epics/base/modules/database/src`, StreamDevice under `/opt/epics/support/StreamDevice/src`); check each yourself and name the lines:
- `boRecord.c`, `process`: when the record is not active, `RVAL` is set from `VAL` before the value is written. A write to `VAL` while the record is active changes `VAL` only. So after a completion, `VAL != RVAL` says: a different value was written while it was busy, and it was not what the record started to send.
- `devboStream.c`, `writeData`: the format `%{0|1}` (ENUM) prints `VAL` as it is when the output is formatted.
- `dbAccess.c`, `dbProcess`: what happens to a record that is processed while active.

# The rule to build
R1. **One internal record per supply, `_out:resend`,** on a fixed 1-second scan. When `ToggleOutput` is not active (`PACT` 0) and its value differs from the value it last sent (`VAL != RVAL`), it processes `ToggleOutput` once, through a database link, under the same hold of the lock set as the check. Argue the one hold from the source, as the comment of `_permit:enforce` does.
R2. **It sends what is in the record,** on or off: that is the gate's latest command. It never changes a value, the request or the gate, and it does not start the sequence `_out:switch` (the REN, and the limit for an on, went out with the sequence whose last step was lost).
R3. **Its value** is the number of times it has done so since the IOC start (0 in a system where nothing went wrong). No alarm of its own. Internal, logging tier `none`.
R4. **It ends.** After its processing `VAL` equals `RVAL` unless a new write came in, also when the supply does not answer. Say it from the source and test it: a supply that is silent is not flooded.
R5. **Nothing is sent twice.** On the event path EPICS already runs the busy record again (RPRO). Say from the source what the rule finds then, also when its evaluation falls between the completion and the queued reprocessing, and show by the line trace that each command goes out once.
R6. **Behaviour kept.** Where no value is written into a busy `ToggleOutput`, nothing changes: a direct write by a client (P28), the front panel, the first contact after an IOC start (the take-over's three steps run under one hold of the lock, so the rule cannot see a state between them: argue it), `_permit:enforce`, the latch, the gate and its scan, the switching sequence. No PV is renamed or changes its type.
R7. **Both databases in step,** with their comments brought up to date: the gate's section says today that its write can be lost and that only `_permit:enforce` covers it.
R8. **Report, do not change** (I decide with the owner), from the source: the one window this rule does not close. The gate writes the selection `SELN` into `_out:switch` while that `seq` is running (between its start and its last link group), without the put flag. My reading: the running sequence's last group reads the gate's value when it runs (`DOL2` at callback time), so the output command follows the gate's latest result in both directions, and what is skipped is only the first step of the other mask (an on that overtakes an off sequence goes out without the limit having been sent again). Confirm or correct this with the lines, and say how long that window is.
R9. **The plan stays the truth.** `_out:resend` in `plan/controls.yaml` for both databases. `python plan/build.py` without warnings. Do not raise the plan's revision. Regenerated files (`registry.json`, `plan/out/`) as a commit of their own at the end.

Lessons of T20 that apply here:
- No input of a rule may wait on a record that is read periodically: with the same period it is busy at every evaluation (a scan list is ordered by record type, `dbScan.c`, `buildScanLists`). `ToggleOutput` is Passive; keep it that way and let the structure test say so.
- A test must not depend on how soon its Channel Access client finds a restarted IOC (it can take longer than `GRACE`).

# Tests
All in the device case `emulation/devtest/matsusada`; the system suite gets no new test (its time budget is used up) and must pass unchanged.

1. **The lost write, made on purpose.** A write without the put flag into a busy `ToggleOutput` cannot be made by a client (a client's write carries the flag). Build a helper that exists in the device case only (its own small database loaded by the case's `ioc.cmd`, never by an IOC's `st.cmd`): a record that a periodic scan processes and that writes a value a test has prepared into `ToggleOutput` through a PP database link. Keep `ToggleOutput` busy long enough with the simulator's `slow` fault. Then, for one AU unit and one REK unit, in both directions (an off lost during a switch-on, an on lost during a switch-off):
   - without the rule (see it once, for example with `_out:resend` disabled): the value is stored and not sent; say what the records and the simulator show;
   - with the rule: the value is sent within one evaluation after the record is free, the supply follows, the count goes up by one, the alarm of `ToggleOutput` is gone.
   Print the timeline of each case (what the IOC wrote to the line and when), so that I can read it in the log.
2. Several values written while busy: the last one is sent. And a row that ends on the value being sent (off, then on, during a switch-on): nothing more is sent, the count does not move.
3. R5: an off by the request (the gate, change event) while a switch-on is on the line: the supply ends off, each command went out once.
4. R4: a value written while busy with a command to a silent supply.
5. An IOC restart with one supply on and one off: both counts (`_out:resend`, `_permit:enforce`) stay 0, nothing is sent beyond what is sent today.
6. The 120 normal permit losses of `test_permit_enforce.py`: also the count of `_out:resend` does not move.
7. The structure, read from the running IOC, including: `ToggleOutput` is Passive.

See every new test fail once without the rule, and say how. The existing tests of the device case and of the suite pass unchanged; if one must change, say which and why.

# Files you own
- `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`
- `emulation/devtest/matsusada` (tests, the helper database, `ioc.cmd`, `mat.py`)
- `emulation/tests/` only where a structure test or a list of internal records must know the new record
- `plan/controls.yaml` (records only), the regenerated registry and `plan/out/`
Not yours: `EPICS/Db/supply_first_contact.db` and the other databases, the IOCs' `st.cmd`, the simulators under `emulation/sim` (if a test needs something a simulator cannot do, report it), `RAS/` except the generated registry, `logger/`, `loops/`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `DESIGN.md`.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock emulation/devtest/run.sh emulation/devtest/matsusada
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
All exit 0, the suite with the saved settings unchanged. The lead then disables the rule himself, runs test 1 and reads its timeline, and runs it again with the rule.

# Rules
- Do not invent facts. A claim about how EPICS processes a record comes with the file and line of the base in our image.
- No change of behaviour beyond this task. If the rule as written here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (step by step with the source lines), R8, VERIFIED (commands, exit codes, times, the timelines of test 1 without and with the rule, and how each new test was seen to fail), DECISIONS, ASSUMED, NEEDS THE LEAD (text for STATUS.md, anything of the plan the lead must do).
