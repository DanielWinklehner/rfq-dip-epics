You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T20: while the output permit of a Matsusada or REK high-voltage supply is lost, the software must keep the output off as a state, not as a single event (open point P45). A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t20`, on branch `emu/t20-permit-enforce`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- In a new worktree the GUI's sources are missing until you run `git submodule update --init` there (needed before `make -C RAS/mist2 dev-up`).
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo.
- **Shared machine.** The emulation (fixed container names, network 172.30.0.0/24, one volume `mist2emu-save` with the IOCs' saved settings) can exist only once. Take the lock for the whole time you have the emulation or a device case up, and bring down what you started before you release it: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`, or a `make` target that starts and stops by itself under `flock /tmp/mist2emu.lock`. Never leave anything running outside the lock, and never stop containers you did not start. If the lock is taken, wait.
- Leave the saved settings as you found them (the suite prints at its start what differs from `limits.defaults`).
- Long commands (the suite takes about 12.6 minutes, the GUI check about 10, the device case 4) may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Leave no container and no process running when you finish.

# Read first
1. `docs/emulation/STATUS.md`: open points P45 (this task) and P28, the block "The supplies' first contact without a gap" under "Done" (what was read in the EPICS source for T19), and question 13.
2. `EPICS/Db/matsusada_au20p7.db` with its header, section "output": `SetToggleOutput`, `_permit:read`, `OutputIntlk` (the gate), `_out:switch`, `_out:limit`, `_out:remote`, `_permit:latch`, `ToggleOutput`, `status:read`, `read_output_status`. `EPICS/Db/rek.db` has the same records with other defaults; the two files are kept in step. `EPICS/Db/supply_first_contact.db` with its header (first contact, `GRACE`, when the gate is enabled).
3. `EPICS/Db/matsusada_co_ctrl.proto` (and `rek.proto`): `toggle_output`, `remote`, `switch_on_limit`, `get_output_status`, `read_status`.
4. The tests of the gate: `emulation/tests/test_06_interlock.py`, `test_10_lost_permit.py`, `test_08_local.py`, `test_11_first_contact.py` (the structure test), `emulation/tests/README.md`, `system.py`; the device case `emulation/devtest/matsusada` (`ioc.cmd`, `permit.db`, `mat.py`, `test_matsusada.py`, `sim.yaml`).
5. The simulator `emulation/sim/mist2sim/devices/matsusada_co.py`: signals `<unit>.sw`, `<unit>.output`, `<unit>.remote`, `<unit>.cutoff`, what it logs, the fault "silent".
6. `plan/README.md`: every record is in `plan/controls.yaml`.

# The fault
The gate `OutputIntlk` starts its switching sequence only when its result changes. The off command of that sequence can be lost: `ToggleOutput` may still be busy with a switch-on (RST, SW1 and the read-back on the line), and EPICS marks a busy record to run again only when the write came through a put (`dbDbLink.c`, `processTarget`: `psrc->putf`), which the gate's own 1-second scan is not. So if the permit is lost while a switch-on is on the line and the gate's scan sees it before the permit's change event arrives, the off value is written into the record and not sent. The supply stays on with the permit lost and its request cleared, and the gate does not try again, because its result no longer changes. The same state arises when a client writes `ToggleOutput` directly while the permit is lost (P28), or when someone switches on at the front panel.

The owner's word (2026-11-23): fix it. The supplies will also have a hardware interlock; the software gate is an extra layer and its state is information for the logger. So: a simple, robust rule, no elaborate machinery.

# The rule to build
"Permit lost" stays what it is today for the gate and the latch: `OutputIntlk.A` non-zero, or `OutputIntlk.C` at least 3 (permit INVALID or disconnected).

R1. **Off as a state.** While the gate is enabled, the permit is lost, and the supply reports its output on by a valid reading, the off sequence of `_out:switch` (mask 6: REN, then RST, SW0 and the read-back) is sent again, and again for as long as the three hold. "Reports on": `read_output_status` (SW?) is ON, or `status:read` (STS) is ON or "ON, LOCAL"; a reading whose record is INVALID does not count.
R2. **One internal record, `_permit:enforce`,** on a fixed 1-second scan (as the gate has). It acts when the condition has held at two evaluations in a row, and then counts from zero again: the first off sequence 1 to 2 s after the IOC has the reading, then one every 2 s while the condition lasts. While a switching command or a read of the SW setting is under way (`_out:switch`, `ToggleOutput` or `read_output_status` active, field `PACT`) the condition counts as not fulfilled. The purpose of both: a normal permit loss sends exactly one off sequence, as today, never two. The check and the start of the sequence run under one hold of the lock set: argue it from the source of the base in our image, as `supply_first_contact.db` does, and name the lines. If one record cannot do it, two, with the reason.
   *Changed in the review (lead, 2026-11-23): `read_output_status` is not among the records whose activity makes the rule wait. It is read periodically, and with its period at 1 second the rule never acted. Only `_out:switch` and `ToggleOutput` remain. See STATUS.md, "The output permit as a state".*
R3. **Its value** is the number of off sequences it has started since the IOC start (0 in a system where nothing went wrong), so that it can be read for diagnosis. No alarm of its own. Internal, logging tier `none`.
R4. **It only switches off.** It never switches on and never writes the request (the latch does that). It starts the same sequence the gate starts, so REN comes first and a supply under local control is taken back and switched off, as the gate does today at a permit loss.
R5. **A supply that does not answer is not flooded.** INVALID readings do not count as on, so the sending stops when the readings turn INVALID. Say from the records how many sequences can go out before that, and test that it stops and that it starts again when the supply answers and still reports on.
R6. **Behaviour kept.** With the permit present nothing changes: a direct write to `ToggleOutput` (P28) and the front panel act as today, and `test_08_local.py` passes unchanged. Before the gate is enabled (first contact plus `GRACE`) nothing is sent. The latch, the gate and the switching sequence are not changed. A normal permit loss sends one off sequence. No PV is renamed or changes its type.
R7. **Both databases in step**, with their headers and comments brought up to date (the PERMIT macro's text, the comment at `ToggleOutput`, the gate's section).
R8. **Report, do not change** (I decide with the owner), each from the source in our image (`docker run --rm --entrypoint sh mist2-ioc:dev -c '...'`, base under `/opt/epics/base/modules/database/src`):
   a. what a write to `SELN` does to a `seq` that is running (`seqRecord.c`);
   b. the same race in the two other directions: an operator's off, or on, written to `SetToggleOutput` while a switching sequence is on the line, and seen by the gate's 1-second scan before the change event arrives. Is the command lost, which state remains, and how does the operator get out of it;
   c. whether giving the gate's periodic evaluation the put flag (for example its scan replaced by a 1-second record that writes `OutputIntlk.PROC` through a CA link) would close all three directions, and what it would change besides.
R9. **The plan stays the truth.** `_permit:enforce` in `plan/controls.yaml` for both databases, and the note of `out_cmd` if it no longer says what happens. `python plan/build.py` without warnings. Do not raise the plan's revision. Regenerated files (`registry.json`, `plan/out/`) as a commit of their own at the end.

Unknown and to stay unknown here: whether the real supplies answer queries under local control (the simulators do: `queries_without_remote: true`, marked ASSUMED in the configuration). If they do not, both readings are INVALID under local control and the rule does not act there; nothing is worse than today. Do not build on it either way.

# Tests
In the device case `emulation/devtest/matsusada`, for one AU unit and one REK unit:
1. The state the fault leaves: permit lost, request off; then `ToggleOutput` written to 1 by a client. The supply goes on (simulator), and within 4 s it is off again: the simulator received REN, RST, SW0 after the SW1, its output and SW setting are off, `ToggleOutput` is 0, the request is 0, the count went up by one.
2. Front panel: permit lost, then the simulator under local control with its SW setting on (signals `<unit>.remote`, `<unit>.sw`). Off and under remote control again within one status poll plus two evaluations plus the sequence.
3. Permit present: the same direct write, and the same front-panel switch-on, stay on over at least 5 s, and the count does not move.
4. A normal permit loss with the output on: the simulator receives SW0 exactly once, the count does not move. Repeat it enough times that a doubled sequence in a few percent of the cases would show (say how many and why).
5. R5: a supply that reports on and then stops answering.
6. An IOC start with the supply on and the permit lost: nothing is sent before `GRACE` is over, then one off sequence, the count stays 0.
7. A unit that is not polled (`SCAN_GET`, `SCAN_STS` Passive: unit 6): say from the records what the rule sees there, and test case 1 for it if it costs little.
8. The structure, read from the running IOC: scan, inputs and output of `_permit:enforce` are the ones its comment names.

In the system suite, one addition and no more: in `test_06_interlock.py`, while the door is open, `ToggleOutput` of every gated supply is written to 1, and all five are off again within the limit (the AU supplies on the rack IOC, the REK on the platform IOC with its permit through Channel Access). **Time:** the suite takes 757 s today and the budget is 13 minutes (780 s); this addition may cost 8 s. Report the suite's time from a run with nothing else on the machine.

See every new test fail once without the rule (for example with `_permit:enforce` disabled) and say how.

The existing tests of the gate, the latch, local control and the first contact pass unchanged. If one of them counted what a supply receives and now sees more, say which and why, and do not loosen it without telling me.

# Files you own
- `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`
- `emulation/tests/` (the one addition and what the structure test needs), `emulation/devtest/matsusada`
- `plan/controls.yaml` (records only), the regenerated registry and `plan/out/`
Not yours: `EPICS/Db/supply_first_contact.db` and the other databases, the simulators under `emulation/sim` (if a test needs something a simulator cannot do, report it), `RAS/` except the generated registry, `logger/`, `loops/`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `DESIGN.md`.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock emulation/devtest/run.sh emulation/devtest/matsusada
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
All exit 0, the suite with the saved settings unchanged and under 13 minutes. The lead then opens the door by hand, writes `ToggleOutput` of one AU supply and of the REK to 1, and reads what the simulators received and when.

# Rules
- Do not invent facts. A claim about how EPICS processes a record comes with the file and line of the base in our image.
- No change of behaviour beyond this task. If the rule as written here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (step by step with the source lines), R8 (a, b, c), VERIFIED (commands, exit codes, times, and how each new test was seen to fail), DECISIONS, ASSUMED, NEEDS THE LEAD (text for STATUS.md, anything of the plan the lead must do).
