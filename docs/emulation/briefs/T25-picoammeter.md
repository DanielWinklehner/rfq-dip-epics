You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T25: the picoammeter of the dipole scan becomes PVs: a protocol file and a database for StreamDevice, a simulator, and a device test case. No hardware is available, and the instrument's model is not confirmed.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t25`, on branch `emu/t25-picoammeter`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch the main checkout or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev`, the IOC in `mist2-ioc:dev`.
- A device case (`emulation/devtest/run.sh <case>`) is its own Compose project on its own network and needs no lock. You do not need the full emulation. Two other engineers work on this machine at the same time (T23, T24), in their own worktrees.
- Long commands may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t25 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- Never run `rm` with a shell variable in its path. Leave no container and no process running when you finish.

# Read first
1. `plan/controls.yaml`: the device `keithley_desk` (and `emit_pico`, the same kind of instrument on the emittance scanner), work package WP11.
2. A device of this system that was written from its manual, as the pattern: `EPICS/Db/aim.proto` and `aim.db` (the ion gauge: header with the sources, a reading that is INVALID while the gauge is off, the request that takes over the device's state through `first_contact.db`), `EPICS/Db/tdk.proto`.
3. `EPICS/README`, section "Alarms"; `EPICS/Db/first_contact.db` with its header.
4. The simulators: `emulation/sim/README.md`, `emulation/sim/mist2sim/devices/edwards_naim.py` and `tdk_genesys.py`, the core's fault modes, `emulation/sim/tests`, `emulation/sim/run_tests.sh`.
5. The device cases `emulation/devtest/naim` and `tdk`; `emulation/devtest/run.sh` (header).

# What is known, and what is not
Known (plan): "Keithley, model tbc", on an "RS-485 to USB converter" at the lab computer, read by LabVIEW today; proposed PVs `pico1:current:get` (A) and `pico1:range:set`.

Not known: the model, and with it the command set; the line (the plan says RS-485, the Keithley picoammeters I know of have RS-232 and GPIB: that is my memory, not a source); the serial settings in use; how the LabVIEW program sets the instrument up.

**Assumption A44, by the lead:** the instrument is a Keithley 6485, on its serial port. You build for that model from its manual, and everything that depends on the model is in the protocol file and the simulator, so that another model costs those two files.

**The manual is the only source.** Get the Model 6485 instruction manual from the maker's web site (Keithley is part of Tektronix). Every command, reply format, default and range in your files carries the manual's section or page. If you cannot get the manual, stop and report that; do not write commands from memory. While you have it, say for the commands you use whether the Model 6487 differs.

# What to build
R1. **Protocol file and database** in `EPICS/Db` (names of your choice, prefix macro with the default `pico1`): the current reading `$(DEVICE):current:get` in A; the range `$(DEVICE):range:set` with the instrument's fixed ranges and automatic ranging, and what the instrument reports back; whatever the manual says must be on or off before a reading means anything (if the instrument has such a state, it gets a request and a read-back, and the reading is INVALID with the number kept while it does not mean anything, as `AIM:getpressure` does); the instrument's identity string, so that the first contact answers which model it is.
R2. **An overflow is INVALID,** not a huge number. Say from the manual what the instrument sends in overflow and how the record sees it.
R3. **An IOC start changes nothing at the instrument.** No reset, no range, no format: if a reply format has to be set for parsing, find a way to parse the default one, or stop and report why not. The requests take over the instrument's state at the first contact (`first_contact.db`, or say why it does not fit).
R4. **Alarms as `EPICS/README` demands:** the instrument silent or sending something else means INVALID within a time you state, and valid again by itself when it answers.
R5. **The rate.** One reading takes the instrument a time that depends on its integration setting. Take the times from the manual, choose the scan period from them with the arithmetic in the database's header, and measure in the case what the simulator gives.
R6. **Simulator** `emulation/sim/mist2sim/devices/`: the commands the protocol file uses, the instrument's state after power-on as the manual gives it, the measuring time, overflow, the value settable through the control port (a later plant model will drive it), the core's faults. Unit tests beside the others, and a line in `emulation/sim/README.md`.
R7. **Serial line in the real port file is not yours:** give the line settings the manual names as defaults, for the lead.
R8. **`docs/emulation/PICOAMMETER.md`:** what is built, each command with its place in the manual, the state after power-on and what an operator must do before a reading means anything, what differs for the 6487, the table of unknowns.

# Tests
A device case `emulation/devtest/picoammeter`:
1. Every PV valid in normal operation; the reading equals the simulator's value in each range and with automatic ranging, to the digits the instrument sends.
2. The state after power-on: what the PVs show, and that the reading is not taken for a measurement while it is none.
3. Overflow: INVALID, and valid again.
4. Silent, garbage, a closed connection: INVALID within the stated time, valid again without an IOC restart.
5. An IOC start with the instrument in a state set from the simulator's side (a range, the states of R1): the requests show that state, and the simulator has received no command that sets anything (count them).
6. The update rate of the reading against the arithmetic of R5.
See each test fail once without the property it checks, and say how.

# Files you own
The new protocol file and database in `EPICS/Db`, the new simulator module with its registration and its unit tests, one line in `emulation/sim/README.md`, `emulation/devtest/picoammeter/**`, `docs/emulation/PICOAMMETER.md`. Not yours: everything else, in particular `plan/controls.yaml`, the registry, the IOCs' `st.cmd` and port files, the simulator's core, the other databases, `emulation/tests`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`. If you find you need a change there, stop at that point and report it with the reason.

The device stays "later" in the plan and is loaded by no IOC of the emulation yet. So `make -C emulation plan-check` must pass unchanged, and the system suite is not touched.

# Acceptance (the lead runs these from your worktree)
    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/picoammeter
    make -C emulation plan-check
All exit 0.

# Rules
- Do not invent facts. A claim about the instrument comes from the manual with its place; a claim about EPICS or StreamDevice from the source in our image (`docker run --rm --entrypoint sh mist2-ioc:dev -c '...'`, base under `/opt/epics/base`, StreamDevice under `/opt/epics/support/StreamDevice/src`).
- No change outside the files you own. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, THE MANUAL (which document, where from, the commands used with their places, what differs for the 6487), HOW IT WORKS (a reading step by step; the first contact), VERIFIED (commands, exit codes, times, how each test was seen to fail), DECISIONS (with reasons), ASSUMED, NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md and for the plan, the line settings for the port file), COMMITS.
