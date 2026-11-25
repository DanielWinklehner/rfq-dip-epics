You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T32: start and stop of the two pumps of the lab's Edwards TIC station (a turbopump and its backing pump on a cart) from the IOC and the GUI. Until now the IOC only reads the station (task T29). The owner, 2026-11-25: "yes, I want to start and stop the pumps from the GUI.", and on the cold cathode gauge (an AIM on the TIC's socket 2): "Does the TIC switch it on automatically or would I go and do it from the panel? If the latter, definitely through the GUI too.", with his rule "The AIMs may not be turned on until the APG shows 1e-2 Torr or lower". The same day both pumps were started and stopped by hand through the TIC's serial line, so the commands and what the controller does after them are SEEN, not assumed.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t32`, on branch `emu/t32-tic-pumps`, already created from `emulated-iocs` (which holds task T31: the gauges on the TIC). Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch `/home/daniel/code/rfq-dip-epics` itself or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04 with Python 3.10. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev`, the IOC in `mist2-ioc:dev`.
- The full emulation exists ONCE on this machine (Compose project `mist2emu`, GUI project `mist2ras`). Every command that starts or uses it goes through the lock: `flock /tmp/mist2emu.lock <command>`. Do not change files the running emulation mounts while a run of yours is going. A device case (`emulation/devtest/run.sh <case>`) is its own project and needs no lock.
- The worktree's git submodule of the GUI is not checked out: `git submodule update --init` in the worktree before anything of the GUI.
- Long commands exceed your tool's time limit: run them in the background, write output and exit code to files in a scratch directory of your own, and look at the files in short steps.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t32 && ...`. Some file tools refuse `.db` files: read them with `cat`.
- Never run `rm` with a shell variable in its path. Leave no container and no process running when you finish.
- The owner's name, e-mail address and project name go into no request to an outside service. Do not edit `docs/emulation/STATUS.md` or `CLAUDE.md` (another session commits to them).

# Read first
1. `docs/emulation/STATUS.md`, the section "Seen on hardware, lab session": the four entries on the TIC of 2026-11-25 (first contact; the backing pump switched on; the turbopump started; the station shut down, with the venting), and the entry with the owner's answer to question 24. These hold every byte that was sent, every reply with its time, and the states and speeds every 5 s. Also answers 62 to 66, questions 24 to 26, open points P70 to P73.
2. `docs/emulation/TIC.md`, `EPICS/Db/tic.db` and `tic.proto` (use `cat`), `emulation/sim/mist2sim/devices/edwards_tic.py` with its tests, `emulation/devtest/tic`.
3. How a pump is started today in this system: `EPICS/Db/turbo_pump.db`, `first_contact.db`, their rules in `plan/controls.yaml` (section `databases`: roles `run_cmd`, `run_state`, `ack`, `test`), the devices `turbo1` and `valves` there, and the system tests that write (`emulation/tests/test_03_write.py`, `test_04_ack.py`, `test_11_first_contact.py`).
4. The GUI: `docs/emulation/gui/LAYOUT.md` section 1.4 (the classes Turbo pump and Valve), the components behind them, and how a confirmation is asked (the vent valve, `confirm` in the plan).
5. The manual of the protocol, Edwards D397-30-880 Issue H (the same source as T29; `TIC.md` says where it was fetched): object 904 and 910 commands, Table 3 (the response codes).

# Seen on the controller (use these, do not replace them by the manual's general words)
- `!C910 1`, `!C910 0`, `!C904 1`, `!C904 0`, each with CR: each answered `*C9xx 0` after 19 ms.
- The state asked right after a command: the turbopump still shows the old state after 32 and 51 ms; the backing pump read 4 after 32 ms at its start and 0 after 25 ms at its stop.
- Backing pump: 0 to 4 and 4 to 0, no state between at 5 s sampling.
- Turbopump up: 0, then 5 "Accelerating" up to about 50 % speed, 4 "Running" from above 50 %, 100 % after 120 s. Down: 7 "Braking" from the first sample down to 0.3 %, then 0, after 105 s. Alert and priority 0 throughout.
- The pump vents itself from the stop command on (its own valve), so the backing pump may be stopped right after the turbopump's stop: that order was used and held.
- The TIC's own settings: no start delay, no slave setup for the turbopump.
- NOT tried: `!C904 1` with the backing pump off; a start while the pump brakes; a command while an IOC polls the same line.

# Decided by the lead (do not change; if one cannot be built as written, stop and report)
D1. **Three requests, nothing else:** the backing pump on and off, the turbopump on and off, and the gauge on socket 2 (the AIM) on and off. No sequence ("system on"), no setup message (`!S`). Each request is one command to the TIC and is acknowledged: the TIC's `*C9xx 0` ends it; any other response code, or none, leaves the request record in alarm with the code's word (Table 3), and the pump's state unchanged in the IOC.
D2. **The read-only database stays read-only:** the requests are new records in a new database file beside `tic.db`, loaded with the same port, so that `tic.db` alone still sends nothing but queries (its device case keeps showing that).
D3. **The read-back is the TIC's own state,** which the IOC already reads every 2 s: a pump counts as running in the states that follow a start (backing pump 1 and 4; turbopump 1, 5 and 4) and as stopped in the others. "At speed" for the turbopump is the speed (95 % or more, one named value), not the state "Running", which the TIC shows from 50 %.
D4. **After an IOC start a request takes over its pump's state without sending anything** (`first_contact.db`, as the valves and the NT 20's start do). A restart of the IOC neither starts nor stops a pump.
D5. **Three refusals in the IOC, each for the hardware's sake, each visible as words:** the turbopump is not started while the backing pump is not on (state 4); the backing pump is not stopped while the turbopump is in a state that follows a start (1, 5, 4); the AIM is not switched on unless the APG's pressure (`TIC:gauge1:getpressure`) is valid and at or below 1e-2 torr, the owner's rule, one named value. A refused request falls back at once and says why, as the supplies' output request does when its permit is lost. No pressure condition for the turbopump: the owner has not given one (question 26). The IOC does not switch the AIM off by itself when the pressure rises: that is the TIC's own setup to do (below), and an automatic action of the IOC needs the owner's word.
D5a. **The gauge request is from the manual only:** `!C914 1` and `!C914 0` (D397-30-880, object 914, 1.7.5 "On = 1, Off = 0") were NOT tried on the controller. Seen for socket 2: the state 5 "Off" with units type 59 while it is off. Build the request and its read-back (on in the states 6 "Striking" and 11 "On") from the manual, mark it so in the files, and make its first use on the real TIC a step of its own in `LAB-SETUP.md`. The socket is a macro.
D5b. **Does the TIC switch the AIM by itself? Read it, read only:** the manual gives each gauge a "slave setup" (`?S913 4`, `?S914 4`: master, units type, on set point, off set point, enable; Table 1). Add the query for socket 2 as a read-only record or records in the READ-ONLY database's style (in the new file, not in `tic.db`), polled slowly (10 s), so that the GUI can say "the TIC switches this gauge by itself at <value>" or "not linked". Its reply was NOT seen on the controller: take the form from the manual, and let a reply of another form end in INVALID with the raw text kept in a string record for the first contact.
D6. **No communication timeout and no automatic stop:** a pump keeps its state when the IOC stops or loses the line.
D7. **Names:** new PVs under the station's prefix in the lab's style, on the pattern of `turbo_pump.db` (`...:start:set`, `...:start:get`, ...), so that the GUI's existing class for a turbopump can show the cart's turbopump with the roles it has; no existing PV is renamed. Propose the names in your report before the GUI depends on them.
D8. **The GUI:** the two pumps as devices of existing widget classes where the roles fit (the turbopump: the class Turbo pump without what it does not have; the backing pump: propose the smallest fit), each with start and stop that ask for confirmation (as the vent valve does), in the vacuum page's list beside the drawing. NOT in the drawings: where the cart sits in the system is not known (question 26).
D9. **The simulator executes the commands as the real controller was seen to:** replies and their times, the backing pump's change at once, the turbopump's states and speed over time with the times above as named configuration values, the old state right after a command. What was not tried on the controller (the three points above) is a named choice of the simulator, marked ASSUMED, and the IOC must not rely on it: D5 keeps the IOC from sending the first two.

# What to build
R1. Protocol entries and the new database file after D1 to D7 (`tic.proto` may get new entries; its existing ones and `tic.db` are not changed unless D3 needs a record there: then say so before you do it).
R2. The simulator after D9, with unit tests.
R3. The device case `emulation/devtest/tic` extended (or a second case beside it): every request with its acknowledgement and read-back; each refusal of D5 with its word (the AIM's at 1.1e-2 torr and with the APG's pressure INVALID); the slave setup read with a link, without one, and with a reply of another form; an error reply and a missing reply to a command; the take-over after an IOC restart with a pump running (nothing sent); a command while the line is polled at the full rate; and still: `tic.db` alone sends only queries.
R4. The rack IOC loads it (`st.cmd`), the plan has it (`plan/controls.yaml`: the devices, the rules of the new database, a new revision with its note; no warning), registry and `plan/out` regenerated, the simulator's configuration as needed.
R5. The system tests cover the new requests as they cover the others (write, acknowledgement, first contact, fault lists).
R6. The GUI after D8, checked with the repository's GUI check, with screenshots.
R7. `docs/emulation/TIC.md`: a section on the control (what is sent, what the IOC refuses, what is not built), and `LAB-SETUP.md`: the first start of a pump from the IOC on the real station as steps for the owner, each with what he should see and what to send back, starting with the backing pump.

# Tests
1. Plan: `flock /tmp/mist2emu.lock sh -c 'make -C emulation registry && make -C emulation plan && make -C emulation plan-check'`, no warning.
2. `emulation/sim/run_tests.sh`; the device case(s). See each property of R3 fail once: say which line you changed and what the test printed.
3. `flock /tmp/mist2emu.lock make -C emulation test`: all pass; give the count before and after and explain the difference.
4. The GUI check, through the lock.
5. The rack IOC starts with the real port file in a container without devices and reaches "iocRun: All initialization complete" (the command is in the brief of T31, test 5).

# Files you own
`EPICS/Db/tic.proto` (new entries), the new database file, `EPICS/ioc/iocBoot/iocRack/st.cmd` (the load lines), `emulation/sim/mist2sim/devices/edwards_tic.py` with its tests, `emulation/sim/config/**` (the TIC's entry), `emulation/devtest/tic/**` or a new case, `plan/controls.yaml`, `plan/out/**`, `plan/build.py`, `plan/registry.py` and `plan/test_build.py` only if a rule is missing, `emulation/tests/**`, `RAS/mist2/ReactApp/src/**`, `docs/emulation/TIC.md`, `docs/emulation/LAB-SETUP.md`, a note under `docs/emulation/gui/` if needed. Not yours: `docs/emulation/STATUS.md`, `CLAUDE.md`, the port files, every other database, everything else.

# Acceptance (the lead runs these from your worktree)
    the plan command of test 1
    emulation/sim/run_tests.sh
    the device case(s) (name them in the report)
    flock /tmp/mist2emu.lock make -C emulation test
    the GUI check (name the exact command)
    the start of the rack IOC with the real port file
All exit 0.

# Rules
- Do not invent facts. What the controller does is in the lab session's record; what the manual says has its place named; what neither says is a named configuration value of the simulator, marked as assumed, and the IOC does not depend on it.
- No change outside the files you own. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT (by R1 to R7), THE NAMES (D7), HOW A REQUEST RUNS (step by step, with the bytes), WHAT THE IOC REFUSES AND HOW IT SAYS SO, VERIFIED (commands, exit codes, counts, how each test was seen to fail), DECISIONS (with reasons), ASSUMED (each with the value that holds it), NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md, the steps for the first start on the real station).
