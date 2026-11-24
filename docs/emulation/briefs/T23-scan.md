You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T23: a Python program that runs a one-dimensional scan through Channel Access only. Its first use is the dipole scan, which the owner wants off LabVIEW (work package WP11 of `plan/controls.yaml`); the emittance scanners follow later with the same tool.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t23`, on branch `emu/t23-scan`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch the main checkout or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev` (pyepics 3.5.8, pytest).
- A device case (`emulation/devtest/run.sh <case>`) is its own Compose project on its own network and needs no lock. The full emulation (`make -C emulation up`, `up-plant`, fixed names, one volume with saved settings) exists only once on this machine: take `flock /tmp/mist2emu.lock <command>` for the whole time you have it up, bring it down before you release the lock, and leave the saved settings as you found them. Two other engineers work on this machine at the same time (T24, T25), in their own worktrees.
- Long commands may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t23 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- Never run `rm` with a shell variable in its path. Leave no container and no process running when you finish.

# Read first
1. `plan/controls.yaml`: work packages WP11 and WP12, the devices `magnets` and `keithley_desk` (their proposed PV names), the section `software`.
2. `loops/`: the loop service is the pattern for a Python program beside the IOCs: logic without an EPICS import (`loop.py`, `pid.py`), the Channel Access side apart (`service.py`), unit tests with a fake Channel Access side (`loops/tests`), `README.md`.
3. `docs/emulation/README.md` sections 3, 4 and 6; `emulation/devtest/run.sh` (header) and `emulation/devtest/compose.yaml`; one small case, for example `emulation/devtest/faradaycup`.
4. `EPICS/README`, section "Alarms": a record of a device that stopped answering is INVALID in this system, it does not keep showing its last value. The scan relies on that.

# What is known, and what is not
The owner's words (2026-11-24): "I want to move the dipole scan off LabView and into the control system or a standalone python script." Decided by the lead: the devices become PVs (tasks T24, T25), the scan is a Python program that is a Channel Access client and talks to nothing else.

Not known, and to stay configuration: everything about the LabVIEW program (range, step, settling, dwell, what it saves), the units, whether the magnet supplies need slow changes. The PV names of the dipole are the plan's proposals: `dipole:current:set`, `dipole:current:get`, `pico1:current:get`. Do not invent values for the machine: every number in a shipped definition is marked ASSUMED where it is one.

# What to build
R1. **Package `scans/mist2scan`**, Python 3.8 or later, PyYAML and pyepics only. The scan logic has no EPICS import and is tested with a fake Channel Access side. Command line: `python -m mist2scan run <definition.yaml>` with overrides for range, step, dwell and output directory, and `python -m mist2scan check <definition.yaml>` that connects, prints what it would do (points, limits, estimated time) and writes nothing.
R2. **Definition (YAML):** one actuator (set PV, read-back PV, tolerance, settle timeout, extra settle time, largest step per move and the pause between part steps, limits), the points (start, stop, step, or a list), detectors (PVs, each required or optional), the dwell time, conditions that must hold during the scan (PV, comparison, value), and what happens at the end (back to the value before the scan, to a given value, or stay). Unknown keys are an error, not ignored.
R3. **One point:** move (in part steps if the move is larger than the largest step), wait until the read-back is within the tolerance and valid, wait the extra settle time, then collect each detector for the dwell time. Nothing collected before the settle is used. A monitor delivers a value only when it changes: say in the document how a detector that holds one value for the whole dwell is counted, and why the mean you compute is the right one for a value that changes in steps.
R4. **Honest data.** A value taken while its PV is INVALID or not connected is not used. A point without a valid value of a detector is recorded as missing for that detector, with the reason, never with an older value. The read-back never reaching the tolerance is a recorded outcome of that point (skip the point or end the scan: configuration), not a silent pass.
R5. **Limits.** The program never writes a value outside the definition's limits or outside the control limits the set PV reports. It refuses to start when the actuator or a required detector is not connected or INVALID, when a condition does not hold, or when the definition would leave the limits. It writes one PV only: the actuator.
R6. **Every end is clean.** Completed, a condition lost, the actuator or a required detector lost, ctrl-c, SIGTERM, an error in the program: in each case the actuator is taken to the configured end value in part steps where it can still be written, the data so far is on disk, and the file says how and why the scan ended and where the actuator was left. Exit codes that tell these apart.
R7. **Files:** one directory per scan. A table with one row per point (set value, read-back, and per detector mean, spread, number of values, minimum, maximum, validity), written row by row while the scan runs, and a file with the definition as it ran, start and end time, the end state and reason, the units and limits read from the PVs, and the version of the program. Text formats a person and `numpy`/`pandas` read without this program.
R8. **Definitions shipped:** `scans/config/dipole.yaml` with the plan's proposed PV names and ASSUMED numbers, and one that runs in today's full emulation with the plant model (extraction voltage against the Faraday cup current: find the PVs in the registry, `RAS/mist2/ReactApp/src/registry/registry.json`).
R9. **Documents:** `scans/README.md` (running it in the tools container and, like `loops/README.md`, in a virtual environment on the lab computer, which runs Ubuntu: marked not verified) and `docs/emulation/SCAN.md` (design, the definition key by key, the file format, a table of what happens at each kind of failure, what is not built).
R10. **Not now, say so under "not built":** two-dimensional scans, scan state as PVs for the GUI and the logger, a GUI page, analysis of the data (peak finding belongs to the tests only).

# Tests
1. Unit tests without EPICS (`python3 -m unittest discover -s scans/tests -t scans`, seconds): the point list (sign of the step, the end point, rounding), part steps, settling and its timeout, the statistics of R3 with constructed sequences, invalid values left out, a missing point, each end of R6 with the actuator's last writes checked, the refusals of R5, rows on disk after an abort, unknown keys.
2. A device case `emulation/devtest/scan` with soft records only, in a database of the case: a set point, a read-back that follows it with a lag, a detector computed from the read-back with three peaks and some noise, a detector that holds one value, a record a test can make INVALID, a condition record. No device simulator is needed (`sim.cmd`). The program runs there as it will run for the owner (`python -m mist2scan run ...`), and the tests read its files: the three peaks are found where the database puts them; read-back means within the tolerance; a detector made INVALID for some points gives missing values exactly there; the condition lost in the middle ends the scan, the actuator goes back in part steps (watch its values with a monitor), the rows so far are in the file; ctrl-c the same; the IOC restarted in the middle (the harness can do it): a clean end, no write after it that the definition does not allow; a required detector not connected at the start: refused; a definition beyond the control limits: refused, nothing written.
3. Once, by hand, in the full emulation with the plant model (lock): the shipped emulation definition from start to end. Put the command, the table and the time it took into the report. No test is added to the system suite (`make -C emulation test`); its time is used up.
See each test of 2 fail once without the property it checks, and say how.

# Files you own
`scans/**`, `emulation/devtest/scan/**`, `docs/emulation/SCAN.md`. Not yours: everything else, in particular `plan/controls.yaml`, the registry, `EPICS/`, `emulation/sim`, `emulation/tests`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`. If the tools image lacks something you need, say so and stop; do not change the image.

# Acceptance (the lead runs these from your worktree)
    python3 -m unittest discover -s scans/tests -t scans          (in mist2-tools:dev: say the exact docker command)
    emulation/devtest/run.sh emulation/devtest/scan
    make -C emulation plan-check
and the hand check of test 3. All exit 0.

# Rules
- Do not invent facts. A claim about how pyepics or Channel Access behaves comes with the source file or the documentation it is read from, or with a test that shows it.
- No change outside the files you own. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (one point step by step; each end of R6), VERIFIED (commands, exit codes, times, how each test was seen to fail), DECISIONS (with reasons), ASSUMED, NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md and for the plan), COMMITS.
